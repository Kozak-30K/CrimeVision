
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ultralytics import RTDETR

from app.services.scene_description import SceneDescriptionService
from app.services.scene_context import SceneContextService
from app.services.video_frame_extraction import extract_video_frames
from app.services.video_scene_analysis import VideoSceneAnalysisService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "video_analysis"

MODEL_NAME = "rtdetr-l.pt"
DEFAULT_CONFIDENCE_THRESHOLD = 0.35


class VideoAnalysisService:
    """Run object detection, captioning, and scene analysis on video."""

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        detector=None,
        captioner=None,
        scene_classifier=None,
        scene_analyzer=None,
    ) -> None:
        self.model_name = model_name

        self.detector = (
            detector
            if detector is not None
            else RTDETR(model_name)
        )

        if captioner is not None:
            self.captioner = captioner
        else:
            captioner_choice = os.getenv(
                "CRIMEVISION_CAPTIONER", "blip"
            ).strip().lower()

            if captioner_choice == "smolvlm2":
                from app.services.smolvlm2_description import (
                    SmolVLM2DescriptionService,
                )

                self.captioner = SmolVLM2DescriptionService()
            elif captioner_choice == "blip":
                self.captioner = SceneDescriptionService()
            else:
                raise ValueError(
                    "Invalid CRIMEVISION_CAPTIONER value. "
                    "Choose 'blip' or 'smolvlm2'."
                )

        self.scene_classifier = (
            scene_classifier
            if scene_classifier is not None
            else SceneContextService()
        )

        self.scene_analyzer = (
            scene_analyzer
            if scene_analyzer is not None
            else VideoSceneAnalysisService()
        )

    def _detect_objects(
        self,
        frame_path: Path,
        confidence_threshold: float,
    ) -> list[dict[str, Any]]:
        results = self.detector.predict(
            source=str(frame_path),
            conf=confidence_threshold,
            verbose=False,
        )

        detections = []

        if not results or results[0].boxes is None:
            return detections

        result = results[0]

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            coordinates = box.xyxy[0].tolist()

            detections.append({
                "label": result.names.get(
                    class_id, str(class_id)
                ),
                "class_id": class_id,
                "confidence": round(confidence, 4),
                "bounding_box": {
                    "x1": round(float(coordinates[0]), 2),
                    "y1": round(float(coordinates[1]), 2),
                    "x2": round(float(coordinates[2]), 2),
                    "y2": round(float(coordinates[3]), 2),
                },
                "requires_review": True,
            })

        return detections

    def analyze_video(
        self,
        video_path: str | Path,
        source_sha256: str,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        sample_interval_seconds: float = 1.0,
        max_frames: int = 120,
    ) -> dict[str, Any]:
        """Analyze an uploaded video and return a structured report."""

        video_path = Path(video_path).expanduser().resolve()

        if not video_path.is_file():
            raise FileNotFoundError(
                f"Video file not found: {video_path}"
            )

        if not source_sha256:
            raise ValueError("The source SHA-256 hash is required.")

        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be between 0 and 1."
            )

        if sample_interval_seconds <= 0:
            raise ValueError(
                "sample_interval_seconds must be greater than zero."
            )

        if not 1 <= max_frames <= 120:
            raise ValueError(
                "max_frames must be between 1 and 120."
            )

        # 1. Extract timestamped frames.
        extraction = extract_video_frames(
            video_path=video_path,
            sample_interval_seconds=sample_interval_seconds,
            max_frames=max_frames,
        )

        frame_observations = []

        # 2. Analyze each extracted frame.
        for frame in extraction["frames"]:
            frame_path = Path(frame["frame_path"]).resolve()

            if not frame_path.is_file():
                raise FileNotFoundError(
                    f"Extracted frame not found: {frame_path}"
                )

            detections = self._detect_objects(
                frame_path=frame_path,
                confidence_threshold=confidence_threshold,
            )

            caption = self.captioner.describe_image(frame_path)

            scene_context = (
                self.scene_classifier.classify_image(frame_path)
            )

            frame_observations.append({
                "frame_index": int(frame["frame_index"]),
                "timestamp_seconds": float(
                    frame["timestamp_seconds"]
                ),
                # Keep absolute paths internally until scene analysis
                # has finished; convert to relative paths for output.
                "frame_path": str(frame_path),
                "frame_file": frame_path.name,
                "width": frame.get("width"),
                "height": frame.get("height"),
                "detections": detections,
                "caption": caption,
                "scene_context": scene_context,
                "requires_review": True,
            })

        # 3. Analyze scene categories across the sampled frames.
        scene_summary = (
            self.scene_analyzer.summarize_scene_context(
                frame_observations
            )
        )

        # 4. Identify large visual differences between adjacent samples.
        scene_changes = self.scene_analyzer.detect_scene_changes(
            frame_observations
        )

        # 5. Convert frame paths to project-relative paths where possible.
        for frame in frame_observations:
            path = Path(frame["frame_path"])

            try:
                frame["frame_path"] = str(
                    path.relative_to(PROJECT_ROOT)
                )
            except ValueError:
                frame["frame_path"] = str(path)

        analyzed_at = datetime.now(timezone.utc).isoformat()

        result = {
            "status": "completed",
            "evidence": {
                "filename": video_path.name,
                "sha256": source_sha256,
                "media_type": "video",
            },
            "video_metadata": {
                "width": None,
                "height": None,
                "fps": extraction["fps"],
                "duration_seconds": extraction[
                    "duration_seconds"
                ],
                "original_frame_count": extraction[
                    "original_frame_count"
                ],
                "sample_interval_seconds": extraction[
                    "sample_interval_seconds"
                ],
                "sampled_frame_count": extraction[
                    "sampled_frame_count"
                ],
            },
            "analysis": {
                "analyzed_at": analyzed_at,
                "object_detection_model": self.model_name,
                "captioning_model": getattr(
                    self.captioner,
                    "model_name",
                    "Salesforce/blip-image-captioning-base",
                ),
                "scene_classification_model": getattr(
                    self.scene_classifier,
                    "model_name",
                    "openai/clip-vit-base-patch32",
                ),
                "confidence_threshold": confidence_threshold,
                "analyzed_frame_count": len(frame_observations),
                "requires_human_review": True,
            },
            "scene_summary": scene_summary,
            "scene_changes": scene_changes,
            "frames": frame_observations,
            "limitations": [
                "Object detections may be incorrect or incomplete.",
                "AI-generated captions may omit or misinterpret details.",
                "Scene classification scores are relative to the candidate labels, not calibrated probabilities.",
                "Visual differences are candidate transitions, not confirmed scene boundaries.",
                "Sampling may miss events occurring between extracted frames.",
                "When the configured frame limit is reached, later portions of the source video are not sampled.",
                "Findings require human review and do not independently establish criminal activity.",
            ],
        }

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )

        output_path = (
            OUTPUT_DIR / f"{source_sha256}_{timestamp}.json"
        )

        try:
            result["output_file"] = str(
                output_path.relative_to(PROJECT_ROOT)
            )
        except ValueError:
            result["output_file"] = str(output_path)

        output_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return result
