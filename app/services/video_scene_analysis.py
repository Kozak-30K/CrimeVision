
from collections import Counter
from pathlib import Path
from typing import Any

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class VideoSceneAnalysisService:
    """Summarize frame context and identify candidate scene changes."""

    def __init__(self, difference_threshold: float = 0.35):
        if not 0.0 < difference_threshold <= 1.0:
            raise ValueError("difference_threshold must be in (0, 1].")

        self.difference_threshold = difference_threshold

    @staticmethod
    def _read_grayscale(image_path: str | Path):
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)

        if image is None:
            raise ValueError(f"Could not read frame: {image_path}")

        # Resize to reduce computation and normalize image dimensions.
        return cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)

    def summarize_scene_context(
        self, frames: list[dict[str, Any]]
    ) -> dict[str, Any]:
        counts = Counter()
        scores_by_category = Counter()
        score_counts = Counter()
        frame_categories = []

        for frame in frames:
            context = frame.get("scene_context") or {}
            category = context.get("predicted_category")

            if not category:
                continue

            counts[category] += 1
            frame_categories.append({
                "frame_index": frame["frame_index"],
                "timestamp_seconds": frame["timestamp_seconds"],
                "category": category,
            })

            for item in context.get("similarity_scores", []):
                score_category = item.get("category")
                score = item.get("score")

                if score_category is not None and isinstance(score, (int, float)):
                    scores_by_category[score_category] += score
                    score_counts[score_category] += 1

        total_classified = sum(counts.values())

        if not total_classified:
            return {
                "status": "unavailable",
                "reason": "No frame scene classifications were available.",
                "classified_frame_count": 0,
                "category_counts": {},
                "category_distribution": {},
                "mean_relative_scores": {},
                "dominant_category": None,
                "frames_disagreeing_with_dominant": [],
                "requires_review": True,
            }

        dominant_category, _ = counts.most_common(1)[0]

        return {
            "status": "completed",
            "classified_frame_count": total_classified,
            "category_counts": dict(counts),
            "category_distribution": {
                category: round(count / total_classified, 4)
                for category, count in counts.items()
            },
            "mean_relative_scores": {
                category: round(
                    scores_by_category[category] / score_counts[category], 4
                )
                for category in scores_by_category
                if score_counts[category]
            },
            "dominant_category": dominant_category,
            "frames_disagreeing_with_dominant": [
                frame for frame in frame_categories
                if frame["category"] != dominant_category
            ],
            "interpretation_note": (
                "The dominant category is the most frequent frame prediction, "
                "not a verified classification of the entire video. Mean scores "
                "are relative CLIP scores, not calibrated probabilities."
            ),
            "requires_review": True,
        }

    def detect_scene_changes(
        self, frames: list[dict[str, Any]]
    ) -> dict[str, Any]:
        ordered_frames = sorted(
            frames, key=lambda frame: frame["timestamp_seconds"]
        )

        changes = []
        previous = None
        compared_pairs = 0
        failed_pairs = []

        for frame in ordered_frames:
            frame_path = frame.get("frame_path")

            if frame_path:
                frame_path = Path(frame_path)

            if not frame_path.is_absolute():
                frame_path = PROJECT_ROOT / frame_path

            frame_path = frame_path.resolve()

            if not frame_path:
                failed_pairs.append({
                    "frame_index": frame.get("frame_index"),
                    "reason": "Missing frame path.",
                })
                previous = None
                continue

            try:
                current_image = self._read_grayscale(frame_path)
            except (ValueError, cv2.error) as exc:
                failed_pairs.append({
                    "frame_index": frame.get("frame_index"),
                    "reason": str(exc),
                })
                previous = None
                continue

            if previous is not None:
                previous_frame, previous_image = previous

                # Mean absolute pixel difference, normalized to [0, 1].
                difference = cv2.absdiff(previous_image, current_image)
                score = float(difference.mean()) / 255.0
                compared_pairs += 1

                if score >= self.difference_threshold:
                    changes.append({
                        "previous_frame_index": previous_frame["frame_index"],
                        "frame_index": frame["frame_index"],
                        "previous_timestamp_seconds": previous_frame[
                            "timestamp_seconds"
                        ],
                        "timestamp_seconds": frame["timestamp_seconds"],
                        "visual_difference_score": round(score, 4),
                        "threshold": self.difference_threshold,
                        "candidate_type": "large_visual_difference",
                        "requires_review": True,
                    })

            previous = (frame, current_image)

        return {
            "method": "resized_grayscale_mean_absolute_difference",
            "difference_threshold": self.difference_threshold,
            "compared_frame_pairs": compared_pairs,
            "candidate_count": len(changes),
            "candidates": changes,
            "failed_frames": failed_pairs,
            "interpretation_note": (
                "Candidates indicate substantial pixel differences, not "
                "confirmed scene boundaries. Camera motion, rapid action, "
                "lighting changes, and animation can also trigger candidates."
            ),
            "requires_review": True,
        }
