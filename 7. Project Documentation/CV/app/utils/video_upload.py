
import hashlib
from pathlib import Path
from uuid import uuid4

import cv2
from flask import current_app, request


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_VIDEO_BYTES = 250 * 1024 * 1024  # 250 MB


def save_uploaded_video():
    if "video" not in request.files:
        return None, {
            "error": "Missing video file. Upload it using the 'video' field."
        }, 400

    uploaded_file = request.files["video"]

    if not uploaded_file.filename:
        return None, {"error": "No file selected."}, 400

    extension = Path(uploaded_file.filename).suffix.lower()

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        return None, {
            "error": "Unsupported video extension.",
            "allowed_extensions": sorted(ALLOWED_VIDEO_EXTENSIONS),
        }, 415

    video_dir = Path(current_app.root_path).parent / "evidence" / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    saved_path = video_dir / f"{uuid4().hex}{extension}"

    try:
        uploaded_file.save(saved_path)

        size_bytes = saved_path.stat().st_size

        if size_bytes == 0:
            saved_path.unlink(missing_ok=True)
            return None, {"error": "The uploaded video is empty."}, 400

        if size_bytes > MAX_VIDEO_BYTES:
            saved_path.unlink(missing_ok=True)
            return None, {"error": "Video exceeds the 250 MB limit."}, 413

        sha256 = hashlib.sha256()

        with saved_path.open("rb") as video_file:
            for chunk in iter(lambda: video_file.read(1024 * 1024), b""):
                sha256.update(chunk)

        capture = cv2.VideoCapture(str(saved_path))

        if not capture.isOpened():
            capture.release()
            saved_path.unlink(missing_ok=True)
            return None, {
                "error": "OpenCV could not open this video. Check the file format or codec."
            }, 415

        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        capture.release()

        if (
            fps <= 0
            or frame_count <= 0
            or width <= 0
            or height <= 0
        ):
            saved_path.unlink(missing_ok=True)
            return None, {
                "error": "Video metadata is invalid or unreadable."
            }, 415

        duration_seconds = frame_count / fps

        return {
            "saved_path": saved_path,
            "source_video": saved_path.name,
            "source_sha256": sha256.hexdigest(),
            "size_bytes": size_bytes,
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration_seconds": duration_seconds,
        }, None, None

    except Exception:
        saved_path.unlink(missing_ok=True)
        raise
