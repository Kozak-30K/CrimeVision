"""Convert video analysis results into forensic observations."""

from app.services.forensic_schema import create_observation


def video_results_to_observations(
    evidence: dict,
    video_result: dict,
) -> list[dict]:
    """Convert frame-level detections and captions into observations."""
    observations = []

    evidence_id = evidence["evidence_id"]
    evidence_sha256 = evidence["sha256"]

    for frame in video_result.get("frames", []):
        timestamp = frame.get("timestamp_seconds")
        frame_index = frame.get("frame_index")

        frame_reference = {
            "type": "video_frame",
            "frame_index": frame_index,
            "timestamp_seconds": timestamp,
            "frame_file": frame.get("frame_file"),
            "frame_path": frame.get("frame_path"),
            "width": frame.get("width"),
            "height": frame.get("height"),
        }

        for detection in frame.get("detections", []):
            label = detection.get("label")
            if not isinstance(label, str) or not label.strip():
                continue

            observations.append(
                create_observation(
                    evidence_id=evidence_id,
                    evidence_sha256=evidence_sha256,
                    modality="video",
                    event_type="object_detection",
                    description=f"Detected object: {label.strip()}",
                    start_time_seconds=timestamp,
                    end_time_seconds=timestamp,
                    source_reference={
                        **frame_reference,
                        "bounding_box": detection.get(
                            "bounding_box", {}
                        ),
                        "coordinate_system": "frame_pixels",
                    },
                    confidence=detection.get("confidence"),
                    model_name=video_result.get(
                        "analysis", {}
                    ).get("object_detection_model"),
                )
            )

        caption_result = frame.get("caption", {})
        caption = (
            caption_result.get("description")
            if isinstance(caption_result, dict)
            else caption_result
        )

        if isinstance(caption, str) and caption.strip():
            observations.append(
                create_observation(
                    evidence_id=evidence_id,
                    evidence_sha256=evidence_sha256,
                    modality="video",
                    event_type="scene_description",
                    description=caption.strip(),
                    start_time_seconds=timestamp,
                    end_time_seconds=timestamp,
                    source_reference=frame_reference,
                    model_name=video_result.get(
                        "analysis", {}
                    ).get("captioning_model"),
                )
            )

        scene_context = frame.get("scene_context")
        if isinstance(scene_context, dict) and scene_context:
            observations.append(
                create_observation(
                    evidence_id=evidence_id,
                    evidence_sha256=evidence_sha256,
                    modality="video",
                    event_type="scene_classification",
                    description=str(scene_context),
                    start_time_seconds=timestamp,
                    end_time_seconds=timestamp,
                    source_reference=frame_reference,
                    model_name=video_result.get(
                        "analysis", {}
                    ).get("scene_classification_model"),
                )
            )

    return observations
