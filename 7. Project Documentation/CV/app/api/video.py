

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from app.utils.video_upload import save_uploaded_video
from app.services.video_analysis import VideoAnalysisService


video_bp = Blueprint("video", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEO_EVIDENCE_DIR = PROJECT_ROOT / "evidence" / "video"


@video_bp.get("/video-frame/<path:relative_path>")
def serve_video_frame(relative_path):
    """Serve only JPEG frames generated beneath the video evidence directory."""
    candidate = (PROJECT_ROOT / relative_path).resolve()
    try:
        candidate.relative_to(VIDEO_EVIDENCE_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Invalid video frame path."}), 400

    # Generated frame files live in per-upload folders ending in _frames.
    if candidate.suffix.lower() not in {".jpg", ".jpeg"} or "_frames" not in candidate.parent.name:
        return jsonify({"error": "Invalid video frame filename."}), 400
    if not candidate.is_file():
        return jsonify({"error": "Video frame not found."}), 404
    return send_file(candidate, mimetype="image/jpeg", as_attachment=False, conditional=True)



def get_video_analysis_service():
    """Reuse the expensive models across requests."""
    service = current_app.extensions.get("crimevision_video_analysis")

    if service is None:
        service = VideoAnalysisService()
        current_app.extensions["crimevision_video_analysis"] = service

    return service


@video_bp.post("/video/analyze")
def analyze_video():
    try:
        metadata, error, status = save_uploaded_video()

        if error:
            return jsonify(error), status

        # Optional parameters are supplied as multipart form fields.
        try:
            confidence_threshold = float(
                request.form.get("confidence_threshold", "0.35")
            )
            sample_interval_seconds = float(
                request.form.get("sample_interval_seconds", "1.0")
            )
            max_frames = int(request.form.get("max_frames", "120"))
        except (TypeError, ValueError):
            return jsonify({
                "error": "Invalid analysis parameters."
            }), 400

        if not 0.0 <= confidence_threshold <= 1.0:
            return jsonify({
                "error": "confidence_threshold must be between 0 and 1."
            }), 400

        if sample_interval_seconds <= 0:
            return jsonify({
                "error": "sample_interval_seconds must be greater than 0."
            }), 400

        # Keep initial CPU workload bounded.
        if not 1 <= max_frames <= 120:
            return jsonify({
                "error": "max_frames must be between 1 and 120."
            }), 400

        service = get_video_analysis_service()

        result = service.analyze_video(
            video_path=metadata["saved_path"],
            source_sha256=metadata["source_sha256"],
            confidence_threshold=confidence_threshold,
            sample_interval_seconds=sample_interval_seconds,
            max_frames=max_frames,
        )

        result["size_bytes"] = metadata["size_bytes"]
        result["video_metadata"]["width"] = metadata["width"]
        result["video_metadata"]["height"] = metadata["height"]
        result["video_metadata"]["fps"] = metadata["fps"]
        result["video_metadata"]["duration_seconds"] = (
            metadata["duration_seconds"]
        )

        return jsonify(result), 200

    except (ValueError, FileNotFoundError) as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception("Video analysis failed")
        return jsonify({
            "error": (
                "Video analysis failed. Check the server logs "
                "for details."
            )
        }), 500
