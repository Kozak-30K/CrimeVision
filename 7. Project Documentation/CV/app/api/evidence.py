
"""Evidence registration API for CrimeVision."""

import hashlib
from pathlib import Path
from uuid import uuid4

from flask import ( Blueprint,  current_app,  jsonify,   request,   send_file)

from app.utils.image_upload import save_uploaded_image
from app.utils.video_upload import save_uploaded_video

evidence_bp = Blueprint("evidence", __name__)

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".wav", ".ogg", ".flac", ".webm"
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024


def get_case_store():
    return current_app.extensions["crimevision_case_store"]


def save_uploaded_audio():
    """Save an audio upload with basic extension and size validation."""
    if "audio" not in request.files:
        return None, {"error": "Missing audio file. Use the 'audio' field."}, 400

    uploaded_file = request.files["audio"]

    if not uploaded_file.filename:
        return None, {"error": "No file selected."}, 400

    extension = Path(uploaded_file.filename).suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        return None, {
            "error": "Unsupported audio extension.",
            "allowed_extensions": sorted(ALLOWED_AUDIO_EXTENSIONS),
        }, 415

    audio_dir = Path(current_app.root_path).parent / "evidence" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    saved_path = audio_dir / f"{uuid4().hex}{extension}"

    try:
        uploaded_file.save(saved_path)
        size_bytes = saved_path.stat().st_size

        if size_bytes == 0:
            saved_path.unlink(missing_ok=True)
            return None, {"error": "The uploaded audio file is empty."}, 400

        if size_bytes > MAX_AUDIO_BYTES:
            saved_path.unlink(missing_ok=True)
            return None, {"error": "Audio exceeds the 25 MB limit."}, 413

        digest = hashlib.sha256()
        with saved_path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)

        return {
            "saved_path": saved_path,
            "sha256": digest.hexdigest(),
            "size_bytes": size_bytes,
        }, None, None

    except Exception:
        saved_path.unlink(missing_ok=True)
        raise


@evidence_bp.post("/cases/<case_id>/evidence")
def register_case_evidence(case_id):
    store = get_case_store()
    saved_path = None

    case = store.get_case(case_id)
    if case is None:
        return jsonify({"error": "Case not found."}), 404

    if case["status"] != "open":
        return jsonify({"error": "Evidence cannot be added to a closed case."}), 409

    modality = request.form.get("modality", "").strip().lower()

    if modality not in {"image", "audio", "video"}:
        return jsonify({
            "error": "modality must be image, audio, or video."
        }), 400

    try:
        if modality == "image":
            saved_path, error, status = save_uploaded_image()
            if error:
                return jsonify(error), status

        elif modality == "video":
            result, error, status = save_uploaded_video()
            if error:
                return jsonify(error), status
            saved_path = result["saved_path"]

        else:
            result, error, status = save_uploaded_audio()
            if error:
                return jsonify(error), status
            saved_path = result["saved_path"]

        metadata = {
            "storage_path": str(saved_path.resolve()),
            "original_filename": request.files[modality].filename,
            "registration_source": "CrimeVision evidence upload",
        }

        if modality == "video":
            metadata["video_metadata"] = {
                "fps": result["fps"],
                "frame_count": result["frame_count"],
                "width": result["width"],
                "height": result["height"],
                "duration_seconds": result["duration_seconds"],
            }

        record = store.register_evidence(
            case_id=case_id,
            file_path=saved_path,
            modality=modality,
            metadata=metadata,
        )

        return jsonify({
            "message": "Evidence registered successfully.",
            "evidence": record,
            "forensic_notice": (
                "The hash identifies the registered file's current contents; "
                "it does not independently establish authenticity or chain of custody."
            ),
        }), 201

    except (ValueError, FileNotFoundError) as exc:
        if saved_path is not None:
            saved_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400

    except Exception:
        if saved_path is not None:
            saved_path.unlink(missing_ok=True)
        current_app.logger.exception("Evidence registration failed")
        return jsonify({"error": "Evidence registration failed."}), 500
@evidence_bp.get("/evidence/<evidence_id>/file")
def get_evidence_file(evidence_id):
    """Serve a registered original evidence file."""
    store = get_case_store()
    record = store.get_evidence(evidence_id)

    if record is None:
        return jsonify({"error": "Evidence not found."}), 404

    metadata = record.get("metadata") or {}
    storage_path = metadata.get("storage_path")

    if not storage_path:
        return jsonify({"error": "Evidence file location is missing."}), 404

    # Evidence files must remain inside the project's evidence directory.
    evidence_root = (
        Path(current_app.root_path).parent / "evidence"
    ).resolve()

    try:
        candidate = Path(storage_path).resolve(strict=True)
        candidate.relative_to(evidence_root)
    except (OSError, ValueError):
        return jsonify({
            "error": "Evidence file is missing or outside evidence storage."
        }), 404

    if not candidate.is_file():
        return jsonify({"error": "Evidence file not found."}), 404

    original_name = Path(
        metadata.get("original_filename")
        or record.get("filename")
        or candidate.name
    ).name

    return send_file(
        candidate,
        as_attachment=request.args.get("download") == "1",
        download_name=original_name,
        conditional=True,
    )