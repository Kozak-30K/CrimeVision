
from pathlib import Path
from uuid import uuid4


from app.services.timeline_normalizer import normalize_timeline
from dotenv import load_dotenv
from app.services.semantic_extraction import SemanticExtractionService
from flask import Blueprint, current_app, jsonify, request
from app.services.event_extraction import extract_events
from app.services.audio_transcription import AudioTranscriptionService


audio_bp = Blueprint("audio", __name__)

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".wav", ".ogg", ".flac", ".webm"
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB


def get_audio_service():
    service = current_app.extensions.get("audio_transcription_service")
    if service is None:
        service = AudioTranscriptionService()
        current_app.extensions["audio_transcription_service"] = service
    return service

def get_semantic_service():
    service = current_app.extensions.get("semantic_extraction_service")

    if service is None:
        # run.py starts Flask directly, so load .env explicitly.
        env_path = Path(current_app.root_path).parent / ".env"
        load_dotenv(dotenv_path=env_path)

        service = SemanticExtractionService()
        current_app.extensions["semantic_extraction_service"] = service

    return service


@audio_bp.post("/transcribe")
def transcribe_audio():
    if "audio" not in request.files:
        return jsonify({
            "error": "Missing audio file. Upload it using the 'audio' field."
        }), 400

    uploaded_file = request.files["audio"]

    if not uploaded_file.filename:
        return jsonify({"error": "No file selected."}), 400

    extension = Path(uploaded_file.filename).suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        return jsonify({
            "error": "Unsupported audio extension.",
            "allowed_extensions": sorted(ALLOWED_AUDIO_EXTENSIONS),
        }), 415

    audio_dir = (
        Path(current_app.root_path).parent / "evidence" / "audio"
    )
    audio_dir.mkdir(parents=True, exist_ok=True)
    saved_path = audio_dir / f"{uuid4().hex}{extension}"

    try:
        uploaded_file.save(saved_path)

        if saved_path.stat().st_size == 0:
            saved_path.unlink(missing_ok=True)
            return jsonify({"error": "The uploaded audio file is empty."}), 400

        if saved_path.stat().st_size > MAX_AUDIO_BYTES:
            saved_path.unlink(missing_ok=True)
            return jsonify({"error": "Audio exceeds the 25 MB limit."}), 413

        requested_language = request.form.get("language") or None
        if requested_language:
            requested_language = requested_language.strip().lower()
            if len(requested_language) not in (2, 3) or not requested_language.isalpha():
                saved_path.unlink(missing_ok=True)
                return jsonify({
                    "error": "Language must be a two- or three-letter language code, such as en, hi, or te."
                }), 400

        result = get_audio_service().transcribe_audio(
            saved_path,
            language=requested_language,
        )
        return jsonify(result), 200

    except ValueError as exc:
        saved_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Audio transcription failed")
        return jsonify({
            "error": "Audio transcription failed. Check the server logs."
        }), 500


@audio_bp.post("/extract-events")
def extract_audio_events():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Send a JSON transcription object in the request body."
        }), 400

    try:
        result = extract_events(payload)
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Audio event extraction failed")
        return jsonify({
            "error": "Event extraction failed. Check the server logs."
        }), 500

@audio_bp.post("/semantic-extract")
def semantic_extract_audio():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Send a JSON transcription object in the request body."
        }), 400

    try:
        result = get_semantic_service().extract(payload)
        return jsonify(result), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        current_app.logger.exception(
            "Semantic audio extraction failed"
        )
        return jsonify({
            "error": "Semantic extraction failed. Check the server logs."
        }), 500


@audio_bp.post("/timeline")
def build_unified_timeline():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Send a JSON object containing keyword_result and semantic_result."
        }), 400

    keyword_result = payload.get("keyword_result")
    semantic_result = payload.get("semantic_result")

    if not isinstance(keyword_result, dict):
        return jsonify({
            "error": "keyword_result must be a JSON object."
        }), 400

    if not isinstance(semantic_result, dict):
        return jsonify({
            "error": "semantic_result must be a JSON object."
        }), 400

    try:
        result = normalize_timeline(
            keyword_result=keyword_result,
            semantic_result=semantic_result,
        )
        return jsonify(result), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        current_app.logger.exception(
            "Unified forensic timeline generation failed"
        )
        return jsonify({
            "error": "Timeline generation failed. Check the server logs."
        }), 500
