
from app.services.observation_adapter import (
    image_results_to_observations,
    audio_result_to_observations,
)


def make_evidence(modality, evidence_id):
    return {
        "evidence_id": evidence_id,
        "sha256": f"hash_{evidence_id}",
        "filename": f"sample.{modality}",
        "modality": modality,
    }


def test_image_results_create_detection_and_caption_observations():
    evidence = make_evidence("image", "ev_image")

    detections = {
        "model": "yolo11n.pt",
        "image_dimensions": {"width": 640, "height": 480},
        "detections": [
            {
                "label": "person",
                "confidence": 0.91,
                "bbox_xyxy": {
                    "x1": 10, "y1": 20, "x2": 100, "y2": 200
                },
            }
        ],
    }
    scene = {
        "model": "Salesforce/blip-image-captioning-base",
        "description": "A person standing near a doorway.",
    }

    observations = image_results_to_observations(
        evidence, detections, scene
    )

    assert len(observations) == 2

    detection, caption = observations

    assert detection["event_type"] == "object_detection"
    assert detection["description"] == "Detected object: person"
    assert detection["confidence"] == 0.91
    assert detection["source_reference"]["coordinates"]["x1"] == 10
    assert detection["evidence_id"] == "ev_image"
    assert detection["evidence_sha256"] == "hash_ev_image"

    assert caption["event_type"] == "scene_description"
    assert caption["description"] == "A person standing near a doorway."
    assert caption["confidence"] is None

    assert all(
        item["review_status"] == "requires_human_review"
        for item in observations
    )


def test_audio_segments_preserve_timestamps():
    evidence = make_evidence("audio", "ev_audio")
    transcription = {
        "model": "base",
        "language": "en",
        "segments": [
            {"start": 1.25, "end": 2.75, "text": "Hello there."},
            {"start": 3.0, "end": 4.0, "text": "Goodbye."},
        ],
    }

    observations = audio_result_to_observations(
        evidence, transcription
    )

    assert len(observations) == 2
    assert observations[0]["event_type"] == "transcribed_speech"
    assert observations[0]["start_time_seconds"] == 1.25
    assert observations[0]["end_time_seconds"] == 2.75
    assert observations[0]["description"] == "Hello there."
    assert observations[0]["model_name"] == "Whisper base"
    assert observations[1]["start_time_seconds"] == 3.0
    assert observations[1]["end_time_seconds"] == 4.0


def test_empty_model_results_return_no_observations():
    evidence_image = make_evidence("image", "ev_empty_image")
    evidence_audio = make_evidence("audio", "ev_empty_audio")

    image_observations = image_results_to_observations(
        evidence_image,
        {"detections": []},
        {},
    )
    audio_observations = audio_result_to_observations(
        evidence_audio,
        {"segments": []},
    )

    assert image_observations == []
    assert audio_observations == []
