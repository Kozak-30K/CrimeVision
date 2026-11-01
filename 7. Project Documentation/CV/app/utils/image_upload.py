
from pathlib import Path
from uuid import uuid4

from flask import current_app, request
from PIL import Image, UnidentifiedImageError


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_PIXELS = 25_000_000


def save_uploaded_image():
    """Validate and save an uploaded image.

    Returns:
        (saved_path, error_response, status_code)
        On success, error_response and status_code are None.
    """
    if "image" not in request.files:
        return None, {"error": "Missing image file. Use the 'image' field."}, 400

    uploaded_file = request.files["image"]

    if not uploaded_file.filename:
        return None, {"error": "No file selected."}, 400

    extension = Path(uploaded_file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return None, {
            "error": "Unsupported file extension.",
            "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        }, 415

    evidence_dir = (
        Path(current_app.root_path).parent / "evidence" / "images"
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)

    saved_path = evidence_dir / f"{uuid4().hex}{extension}"

    try:
        uploaded_file.save(saved_path)

        with Image.open(saved_path) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                saved_path.unlink(missing_ok=True)
                return None, {
                    "error": "Image dimensions exceed the permitted limit."
                }, 413

            image.verify()

        # Reopen and force decoding to catch truncated or invalid image data.
        with Image.open(saved_path) as image:
            image.load()

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        saved_path.unlink(missing_ok=True)
        return None, {
            "error": "The uploaded file is not a valid supported image."
        }, 400

    return saved_path, None, None
