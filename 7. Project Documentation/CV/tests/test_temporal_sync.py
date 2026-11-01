import math

import pytest

from app.services.temporal_sync import synchronize_observations


def observation(evidence_id, start=5.0, end=6.0):
    return {
        "observation_id": f"obs_{evidence_id}",
        "evidence_id": evidence_id,
        "start_time_seconds": start,
        "end_time_seconds": end,
    }


def test_verified_offset_aligns_timestamps():
    result = synchronize_observations(
        [observation("audio", 5.0, 6.0)],
        offsets_seconds={"audio": 10.0},
    )

    item = result["timeline"][0]
    assert item["global_start_seconds"] == 15.0
    assert item["global_end_seconds"] == 16.0
    assert item["synchronization_status"] == "aligned"
    assert item["applied_offset_seconds"] == 10.0


def test_shared_time_origin_uses_zero_offset():
    result = synchronize_observations(
        [observation("video", 2.25, 3.5)],
        shared_time_origin=True,
    )

    item = result["timeline"][0]
    assert item["global_start_seconds"] == 2.25
    assert item["global_end_seconds"] == 3.5
    assert item["applied_offset_seconds"] == 0.0


def test_missing_offset_keeps_observation_unaligned():
    result = synchronize_observations([observation("audio")])

    assert result["aligned_count"] == 0
    assert result["unsynchronized_count"] == 1
    assert result["timeline"][0]["global_start_seconds"] is None
    assert result["timeline"][0]["synchronization_status"] == "unverified"


def test_aligned_observations_sort_before_unaligned():
    result = synchronize_observations(
        [
            observation("unknown", 1.0, 2.0),
            observation("known", 8.0, 9.0),
        ],
        offsets_seconds={"known": 2.0},
    )

    assert result["timeline"][0]["evidence_id"] == "known"
    assert result["timeline"][1]["evidence_id"] == "unknown"

def test_input_observations_are_not_mutated():
    original = observation("audio")
    before = original.copy()

    synchronize_observations(
        [original],
        offsets_seconds={"audio": 2.0},
    )

    assert original == before


@pytest.mark.parametrize("offset", [math.nan, math.inf, -math.inf])
def test_non_finite_offsets_are_rejected(offset):
    with pytest.raises(ValueError):
        synchronize_observations(
            [observation("audio")],
            offsets_seconds={"audio": offset},
        )


@pytest.mark.parametrize("start,end", [(-1.0, 2.0), (3.0, 2.0), (True, 2.0)])
def test_invalid_timestamps_are_rejected(start, end):
    with pytest.raises(ValueError):
        synchronize_observations(
            [observation("audio", start, end)],
            shared_time_origin=True,
        )


def test_non_list_input_is_rejected():
    with pytest.raises(ValueError):
        synchronize_observations("not a list")
