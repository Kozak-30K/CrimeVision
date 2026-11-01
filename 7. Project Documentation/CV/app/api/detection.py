
from pathlib import Path

from flask import Blueprint, current_app, jsonify, send_from_directory

from app.utils.image_upload import save_uploaded_image
from app.services.object_detection import ObjectDetectionService
from app.services.scene_description import SceneDescriptionService


detection_bp = Blueprint("detection", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DETECTION_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "detections"


def get_object_detection_service():
    service = current_app.extensions.get("object_detection_service")
    if service is None:
        service = ObjectDetectionService()
        current_app.extensions["object_detection_service"] = service
    return service


def get_scene_description_service():
    service = current_app.extensions.get("scene_description_service")
    if service is None:
        service = SceneDescriptionService()
        current_app.extensions["scene_description_service"] = service
    return service


@detection_bp.get("/detection-output/<path:filename>")
def serve_detection_output(filename):
    # Serve only generated annotated JPEGs from the dedicated output folder.
    if not filename.endswith("_annotated.jpg") or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid detection output filename."}), 400

    if not (DETECTION_OUTPUT_DIR / filename).is_file():
        return jsonify({"error": "Detection output not found."}), 404

    return send_from_directory(
        DETECTION_OUTPUT_DIR,
        filename,
        mimetype="image/jpeg",
        as_attachment=False,
    )


@detection_bp.post("/detect")
def detect_image():
    saved_path, error, status = save_uploaded_image()
    if error:
        return jsonify(error), status

    try:
        result = get_object_detection_service().analyze_image(saved_path)
        return jsonify(result), 200
    except Exception:
        current_app.logger.exception("Object detection failed")
        return jsonify({"error": "Image analysis failed. Check server logs."}), 500


@detection_bp.post("/describe")
def describe_image():
    saved_path, error, status = save_uploaded_image()
    if error:
        return jsonify(error), status

    try:
        result = get_scene_description_service().describe_image(saved_path)
        return jsonify(result), 200
    except Exception:
        current_app.logger.exception("Scene description failed")
        return jsonify({"error": "Scene description failed. Check server logs."}), 500


@detection_bp.post("/analyze")
def analyze_image():
    saved_path, error, status = save_uploaded_image()
    if error:
        return jsonify(error), status

    try:
        detections = get_object_detection_service().analyze_image(saved_path)
        description = get_scene_description_service().describe_image(saved_path)

        return jsonify({
            "analysis_type": "multimodal_image_analysis",
            "source_image": saved_path.name,
            "object_detection": detections,
            "scene_description": description,
            "notice": (
                "AI-generated preliminary analysis. "
                "Verify all findings against the original evidence."
            ),
        }), 200

    except Exception:
        current_app.logger.exception("Combined image analysis failed")
        return jsonify({
            "error": "Combined image analysis failed. Check server logs."
        }), 500
