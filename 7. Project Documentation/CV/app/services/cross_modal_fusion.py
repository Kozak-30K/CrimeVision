"""Conservative cross-modal association of forensic observations."""

from copy import deepcopy
from itertools import combinations
import math

from app.services.temporal_sync import synchronize_observations


def _validate_window(window_seconds):
    if (
        isinstance(window_seconds, bool)
        or not isinstance(window_seconds, (int, float))
        or not math.isfinite(window_seconds)
        or window_seconds < 0
    ):
        raise ValueError("window_seconds must be a finite, non-negative number.")


def _interval_distance(a, b):
    """Return the gap between two intervals; zero means they overlap."""
    a_start = a.get("global_start_seconds")
    a_end = a.get("global_end_seconds")
    b_start = b.get("global_start_seconds")
    b_end = b.get("global_end_seconds")

    if a_start is None or b_start is None:
        return None

    # A missing end timestamp is treated as a point observation.
    a_end = a_start if a_end is None else a_end
    b_end = b_start if b_end is None else b_end

    if a_start <= b_end and b_start <= a_end:
        return 0.0

    return round(max(a_start - b_end, b_start - a_end), 3)


def _references_observation(observation, other_id, field):
    references = observation.get(field) or []

    if not isinstance(references, list):
        return False

    for reference in references:
        if isinstance(reference, str) and reference == other_id:
            return True
        if isinstance(reference, dict) and (
            reference.get("observation_id") == other_id
            or reference.get("evidence_id") == other_id
        ):
            return True

    return False


def fuse_observations(
    observations,
    offsets_seconds=None,
    shared_time_origin=False,
    window_seconds=2.0,
):
    """
    Associate observations from different modalities for human review.

    Temporal proximity alone never establishes corroboration or conflict.
    """
    _validate_window(window_seconds)

    if not isinstance(observations, list):
        raise ValueError("observations must be a list.")

    seen_ids = set()
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ValueError(f"Observation {index} must be an object.")

        observation_id = observation.get("observation_id")
        if observation_id is not None:
            if observation_id in seen_ids:
                raise ValueError("Duplicate observation_id detected.")
            seen_ids.add(observation_id)

    synchronization = synchronize_observations(
        observations,
        offsets_seconds=offsets_seconds,
        shared_time_origin=shared_time_origin,
    )

    timeline = synchronization["timeline"]
    associations = []

    for a, b in combinations(timeline, 2):
        # Same-modality and same-evidence pairs are not cross-modal links.
        if a.get("modality") == b.get("modality"):
            continue
        if a.get("evidence_id") == b.get("evidence_id"):
            continue

        distance = _interval_distance(a, b)

        # Never compare an unaligned observation against a fabricated time.
        if distance is None or distance > window_seconds:
            continue

        a_id = a.get("observation_id")
        b_id = b.get("observation_id")

        explicit_conflict = (
            (b_id and _references_observation(a, b_id, "conflicting_evidence"))
            or (a_id and _references_observation(b, a_id, "conflicting_evidence"))
            or (
                b.get("evidence_id")
                and _references_observation(
                    a, b["evidence_id"], "conflicting_evidence"
                )
            )
            or (
                a.get("evidence_id")
                and _references_observation(
                    b, a["evidence_id"], "conflicting_evidence"
                )
            )
        )

        explicit_support = (
            (b_id and _references_observation(a, b_id, "supporting_evidence"))
            or (a_id and _references_observation(b, a_id, "supporting_evidence"))
            or (
                b.get("evidence_id")
                and _references_observation(
                    a, b["evidence_id"], "supporting_evidence"
                )
            )
            or (
                a.get("evidence_id")
                and _references_observation(
                    b, a["evidence_id"], "supporting_evidence"
                )
            )
        )

        if explicit_conflict:
            relationship = "conflict_flag_for_review"
        elif explicit_support:
            relationship = "support_link_for_review"
        elif (
            a.get("event_type")
            and a.get("event_type") == b.get("event_type")
        ):
            relationship = "potential_corroboration_review"
        else:
            relationship = "temporal_association"

        associations.append({
            "association_id": f"assoc_{len(associations) + 1:04d}",
            "observation_ids": [a_id, b_id],
            "evidence_ids": [a.get("evidence_id"), b.get("evidence_id")],
            "modalities": [a.get("modality"), b.get("modality")],
            "temporal_distance_seconds": distance,
            "relationship": relationship,
            "review_status": "requires_human_review",
            "interpretation_note": (
                "This is a candidate relationship, not proof that the "
                "observations describe the same event."
            ),
        })

    return {
        "analysis_type": "cross_modal_fusion",
        "observation_count": len(timeline),
        "association_count": len(associations),
        "aligned_count": synchronization["aligned_count"],
        "unsynchronized_count": synchronization["unsynchronized_count"],
        "timeline": timeline,
        "associations": associations,
        "limitations": [
            "Only observations with aligned timestamps can be associated.",
            "Temporal proximity does not prove a shared event.",
            "Matching event types are candidate corroboration, not confirmation.",
            "Conflict and support flags rely on explicit existing evidence links.",
            "All associations require human review.",
        ],
    }
