from app.services.cross_modal_fusion import fuse_observations


def make_observation(
    observation_id,
    evidence_id,
    modality,
    event_type,
    start,
    end=None,
):
    return {
        "observation_id": observation_id,
        "evidence_id": evidence_id,
        "evidence_sha256": f"hash_{evidence_id}",
        "modality": modality,
        "event_type": event_type,
        "description": f"Test observation {observation_id}",
        "start_time_seconds": start,
        "end_time_seconds": end,
        "source_reference": {},
        "confidence": 0.8,
        "model_name": "test-model",
        "supporting_evidence": [],
        "conflicting_evidence": [],
        "review_status": "requires_human_review",
        "schema_version": "1.0",
    }


def run_tests():
    observations = [
        make_observation("obs_audio", "ev_audio", "audio", "impact", 5.0, 5.5),
        make_observation("obs_video", "ev_video", "video", "impact", 6.0, 6.5),
        make_observation("obs_image", "ev_image", "image", "impact", 5.2),
        make_observation("obs_far", "ev_far", "video", "impact", 20.0, 21.0),
    ]

    result = fuse_observations(
        observations,
        shared_time_origin=True,
        window_seconds=2.0,
    )

    assert result["observation_count"] == 4
    assert result["aligned_count"] == 4

    # Audio/video and image/audio/video may be associated if within the window.
    pairs = {
        frozenset(item["observation_ids"])
        for item in result["associations"]
    }
    assert frozenset({"obs_audio", "obs_video"}) in pairs
    assert frozenset({"obs_audio", "obs_image"}) in pairs
    assert all(
        item["review_status"] == "requires_human_review"
        for item in result["associations"]
    )

    # Matching event types are only candidate corroboration.
    audio_video = next(
        item for item in result["associations"]
        if set(item["observation_ids"]) == {"obs_audio", "obs_video"}
    )
    assert audio_video["relationship"] == "potential_corroboration_review"

    # An image without a verified common time remains unaligned.
    unaligned = fuse_observations(
        [observations[0], observations[2]],
        shared_time_origin=False,
        window_seconds=2.0,
    )
    assert unaligned["unsynchronized_count"] == 2
    assert unaligned["association_count"] == 0

    # Invalid time windows must be rejected.
    try:
        fuse_observations(observations, window_seconds=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("Negative time window should be rejected.")

    print("PASS: Cross-modal fusion tests succeeded.")
    print(f"Observations: {result['observation_count']}")
    print(f"Associations: {result['association_count']}")
    print(f"Unverified: {result['unsynchronized_count']}")


def test_cross_modal_fusion():
    run_tests()


def test_explicit_support_link_is_classified_for_review():
    audio = make_observation(
        "obs_audio", "ev_audio", "audio", "impact", 5.0, 5.5
    )
    video = make_observation(
        "obs_video", "ev_video", "video", "impact", 5.0, 5.5
    )
    audio["supporting_evidence"] = ["obs_video"]

    result = fuse_observations(
        [audio, video], shared_time_origin=True
    )

    assert result["association_count"] == 1
    assert result["associations"][0]["relationship"] == (
        "support_link_for_review"
    )
    assert result["associations"][0]["review_status"] == (
        "requires_human_review"
    )


def test_explicit_conflict_link_is_flagged_for_review():
    audio = make_observation(
        "obs_audio", "ev_audio", "audio", "impact", 5.0, 5.5
    )
    video = make_observation(
        "obs_video", "ev_video", "video", "impact", 5.0, 5.5
    )
    audio["conflicting_evidence"] = [
        {"evidence_id": "ev_video"}
    ]

    result = fuse_observations(
        [audio, video], shared_time_origin=True
    )

    assert result["association_count"] == 1
    assert result["associations"][0]["relationship"] == (
        "conflict_flag_for_review"
    )


def test_conflict_takes_precedence_when_both_links_exist():
    audio = make_observation(
        "obs_audio", "ev_audio", "audio", "impact", 5.0, 5.5
    )
    video = make_observation(
        "obs_video", "ev_video", "video", "impact", 5.0, 5.5
    )
    audio["supporting_evidence"] = ["obs_video"]
    audio["conflicting_evidence"] = ["obs_video"]

    result = fuse_observations(
        [audio, video], shared_time_origin=True
    )

    assert result["associations"][0]["relationship"] == (
        "conflict_flag_for_review"
    )


def test_same_modality_pairs_are_excluded():
    observations = [
        make_observation("obs_1", "ev_1", "audio", "impact", 5.0),
        make_observation("obs_2", "ev_2", "audio", "impact", 5.1),
    ]

    result = fuse_observations(
        observations, shared_time_origin=True
    )

    assert result["association_count"] == 0


def test_same_evidence_pairs_are_excluded():
    observations = [
        make_observation("obs_1", "ev_same", "audio", "impact", 5.0),
        make_observation("obs_2", "ev_same", "video", "impact", 5.1),
    ]

    result = fuse_observations(
        observations, shared_time_origin=True
    )

    assert result["association_count"] == 0


def test_window_boundary_is_included_but_outside_is_excluded():
    observations = [
        make_observation("obs_1", "ev_1", "audio", "impact", 1.0),
        make_observation("obs_2", "ev_2", "video", "impact", 3.0),
        make_observation("obs_3", "ev_3", "image", "impact", 3.001),
    ]

    result = fuse_observations(
        observations,
        shared_time_origin=True,
        window_seconds=2.0,
    )

    pairs = {
        frozenset(item["observation_ids"])
        for item in result["associations"]
    }

    assert frozenset({"obs_1", "obs_2"}) in pairs
    assert frozenset({"obs_1", "obs_3"}) not in pairs


def test_invalid_observation_container_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        fuse_observations("not a list")


def test_non_finite_window_is_rejected():
    import math
    import pytest

    for window in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            fuse_observations([], window_seconds=window)
