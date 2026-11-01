
"""Convert modality-specific model outputs into forensic observations."""

from app.services.forensic_schema import create_observation


def image_results_to_observations(
    evidence: dict,
    detection_result: dict,
    scene_result: dict,
) -> list[dict]:
    """Convert image detections and caption into reviewable observations."""
    observations = []

    evidence_id = evidence["evidence_id"]
    evidence_sha256 = evidence["sha256"]

    for detection in detection_result.get("detections", []):
        label = detection.get("label")
        if not isinstance(label, str) or not label.strip():
            continue

        confidence = detection.get("confidence")
        bbox = detection.get("bbox_xyxy", {})

        observations.append(
            create_observation(
                evidence_id=evidence_id,
                evidence_sha256=evidence_sha256,
                modality="image",
                event_type="object_detection",
                description=f"Detected object: {label.strip()}",
                source_reference={
                    "type": "bounding_box",
                    "coordinates": bbox,
                    "coordinate_system": "image_pixels",
                    "image_width": detection_result.get(
                        "image_dimensions", {}
                    ).get("width"),
                    "image_height": detection_result.get(
                        "image_dimensions", {}
                    ).get("height"),
                },
                confidence=confidence,
                model_name=detection_result.get("model"),
            )
        )

    caption = scene_result.get("description")
    if isinstance(caption, str) and caption.strip():
        observations.append(
            create_observation(
                evidence_id=evidence_id,
                evidence_sha256=evidence_sha256,
                modality="image",
                event_type="scene_description",
                description=caption.strip(),
                source_reference={
                    "type": "whole_image",
                    "filename": evidence.get("filename"),
                },
                model_name=scene_result.get("model"),
            )
        )

    return observations


def audio_result_to_observations(
    evidence: dict,
    transcription_result: dict,
) -> list[dict]:
    """Convert timestamped transcription segments into observations."""
    observations = []

    for segment in transcription_result.get("segments", []):
        text = segment.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        observations.append(
            create_observation(
                evidence_id=evidence["evidence_id"],
                evidence_sha256=evidence["sha256"],
                modality="audio",
                event_type="transcribed_speech",
                description=text.strip(),
                start_time_seconds=segment.get("start"),
                end_time_seconds=segment.get("end"),
                source_reference={
                    "type": "transcription_segment",
                    "language": transcription_result.get("language"),
                },
                model_name=(
                    f"Whisper {transcription_result.get('model', 'unknown')}"
                ),
            )
        )

    return observations
