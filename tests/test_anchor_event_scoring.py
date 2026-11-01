import pytest

from app.services.anchor_event_scoring import identify_anchor_events


def observation(
    observation_id,
    evidence_id,
    confidence,
    aligned=True,
    supporting=None,
    conflicting=None,
):
    return {
        "observation_id": observation_id,
        "evidence_id": evidence_id,
        "evidence_sha256": f"hash_{evidence_id}",
        "modality": "video",
        "event_type": "movement",
        "description": f"Observation {observation_id}",
        "global_start_seconds": 4.0 if aligned else None,
        "global_end_seconds": 5.0 if aligned else None,
        "synchronization_status": "aligned" if aligned else "unverified",
        "source_reference": {"frame_index": 4},
        "confidence": confidence,
        "supporting_evidence": supporting or [],
        "conflicting_evidence": conflicting or [],
        "review_status": "requires_human_review",
    }


def test_scores_are_explainable_and_ranked():
    observations = [
        observation("obs_a", "ev_a", 0.9, supporting=["ev_b", "ev_c"]),
        observation("obs_b", "ev_b", 0.4, aligned=False),
        observation("obs_c", "ev_c", 0.7, conflicting=["ev_a"]),
    ]

    result = identify_anchor_events(observations, minimum_score=30)

    assert result["observation_count"] == 3
    assert result["ranked_observations"][0]["observation_id"] == "obs_a"

    for item in result["ranked_observations"]:
        assert 0 <= item["review_priority_score"] <= 100
        assert item["review_status"] == "requires_human_review"
        assert set(item["score_factors"]) == {
            "confidence",
            "cross_modal_support",
            "temporal_alignment",
            "explicit_conflict",
        }


def test_unaligned_observation_has_no_anchor_timestamp():
    result = identify_anchor_events(
        [observation("obs_x", "ev_x", 0.9, aligned=False)]
    )

    item = result["ranked_observations"][0]
    assert item["start_time_seconds"] is None
    assert item["score_factors"]["temporal_alignment"] == 0.0


def test_invalid_confidence_is_rejected():
    with pytest.raises(ValueError):
        identify_anchor_events(
            [observation("obs_x", "ev_x", 1.5)]
        )


def test_invalid_threshold_is_rejected():
    with pytest.raises(ValueError):
        identify_anchor_events([], minimum_score=101)


def test_duplicate_observation_ids_are_rejected():
    duplicate = observation("same", "ev_a", 0.8)
    with pytest.raises(ValueError):
        identify_anchor_events([duplicate, duplicate])
