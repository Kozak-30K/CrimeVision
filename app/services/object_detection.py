
from pathlib import Path
from datetime import datetime, timezone
import json

from PIL import Image, ImageDraw
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "detections"

# Small pretrained model; runs on CPU.
MODEL_NAME = "yolo11n.pt"


class ObjectDetectionService:
    """Detect supported objects in an image and export structured results."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.model = YOLO(model_name)

    def analyze_image(
        self,
        image_path: str | Path,
        confidence_threshold: float = 0.35,
    ) -> dict:
        image_path = Path(image_path).expanduser().resolve()

        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")

        # Validate the image and record its dimensions.
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            image_width, image_height = image.size

        # CPU inference. No original evidence file is modified.
        results = self.model.predict(
        source=str(image_path),
        device="cpu",
        conf=confidence_threshold,
        iou=0.45,
        verbose=False,)

        detections = []
        result = results[0]

        if result.boxes is not None:
            for box in result.boxes:
                class_id = int(box.cls.item())
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = [
                    round(float(value), 2)
                    for value in box.xyxy[0].tolist()
                ]

                detections.append({
                    "class_id": class_id,
                    "label": self.model.names[class_id],
                    "confidence": round(confidence, 4),
                    "bbox_xyxy": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                    },
                })

        people_count = sum(
            detection["label"].lower() == "person"
            for detection in detections
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_stem = f"{image_path.stem}_{timestamp}"

        annotated_path = OUTPUT_DIR / f"{output_stem}_annotated.jpg"
        json_path = OUTPUT_DIR / f"{output_stem}.json"

        # Draw detections on a copy, never on the original evidence.
        with Image.open(image_path) as image:
            annotated = image.convert("RGB")
        draw = ImageDraw.Draw(annotated)

        for detection in detections:
            bbox = detection["bbox_xyxy"]
            coordinates = (
                bbox["x1"], bbox["y1"],
                bbox["x2"], bbox["y2"],
            )
            label = (
                f'{detection["label"]} '
                f'{detection["confidence"]:.2f}'
            )
            draw.rectangle(coordinates, outline="red", width=3)
            draw.text(
                (bbox["x1"], max(0, bbox["y1"] - 14)),
                label,
                fill="red",
            )

        annotated.save(annotated_path, quality=95)

        output = {
            "analysis_type": "object_detection",
            "source_image": image_path.name,
            "image_dimensions": {
                "width": image_width,
                "height": image_height,
            },
            "model": self.model_name,
            "device": "cpu",
            "confidence_threshold": confidence_threshold,
            "analyzed_at_utc": datetime.now(timezone.utc).isoformat(),
            "people_count": people_count,
            "detection_count": len(detections),
            "detections": detections,
            "annotated_image": str(annotated_path.relative_to(PROJECT_ROOT)),
            "limitations": [
                "Predictions require human verification.",
                "A generic model may not detect weapons reliably.",
                "Detections alone do not establish criminal activity.",
            ],
        }

        json_path.write_text(
            json.dumps(output, indent=2),
            encoding="utf-8",
        )

        output["json_output"] = str(json_path.relative_to(PROJECT_ROOT))
        return output
