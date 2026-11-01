"""Identify candidate anchor events and calculate explainable review priority."""

from copy import deepcopy
import math


DEFAULT_WEIGHTS = {
    "confidence": 0.35,
    "cross_modal_support": 0.30,
    "temporal_alignment": 0.20,
    "explicit_conflict": 0.15,
}


def _validate_weights(weights):
    if not isinstance(weights, dict):
        raise ValueError("weights must be a dictionary.")

    if set(weights) != set(DEFAULT_WEIGHTS):
        raise ValueError(
            f"weights must contain exactly: {', '.join(DEFAULT_WEIGHTS)}"
        )

    for name, value in weights.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"Weight '{name}' must be finite and non-negative.")

    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one weight must be greater than zero.")

    return {name: value / total for name, value in weights.items()}


def _confidence_score(observation):
    confidence = observation.get("confidence")

    if confidence is None:
        return 0.0

    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("Observation confidence must be between 0 and 1.")

    return float(confidence)


def _linked_evidence_ids(observation, field):
    """Extract evidence IDs from explicitly recorded links."""
    references = observation.get(field) or []

    if not isinstance(references, list):
        return set()

    result = set()

    for reference in references:
        if isinstance(reference, str):
            result.add(reference)
        elif isinstance(reference, dict):
            evidence_id = reference.get("evidence_id")
            if isinstance(evidence_id, str):
                result.add(evidence_id)

    return result


def _score_observation(observation, weights, linked_support_count):
    confidence = _confidence_score(observation)

    aligned = (
        observation.get("synchronization_status") == "aligned"
        and observation.get("global_start_seconds") is not None
    )
    temporal_score = 1.0 if aligned else 0.0

    # This measures explicitly linked support, not mere timestamp proximity.
    support_score = min(linked_support_count / 2.0, 1.0)

    conflicts = _linked_evidence_ids(observation, "conflicting_evidence")
    conflict_score = 1.0 if conflicts else 0.0

    factors = {
        "confidence": confidence,
        "cross_modal_support": support_score,
        "temporal_alignment": temporal_score,
        "explicit_conflict": conflict_score,
    }

    score = sum(
        weights[name] * factors[name]
        for name in weights
    )

    return round(score * 100, 2), factors


def identify_anchor_events(
    observations,
    associations=None,
    weights=None,
    minimum_score=30.0,
):
    """
    Rank candidate anchor events for investigator review.

    Score means review priority only. It is not event probability,
    evidential certainty, or a measure of guilt.
    """
    if not isinstance(observations, list):
        raise ValueError("observations must be a list.")

    if (
        isinstance(minimum_score, bool)
        or not isinstance(minimum_score, (int, float))
        or not math.isfinite(minimum_score)
        or not 0 <= minimum_score <= 100
    ):
        raise ValueError("minimum_score must be between 0 and 100.")

    normalized_weights = _validate_weights(
        DEFAULT_WEIGHTS if weights is None else weights
    )

    associations = [] if associations is None else associations
    if not isinstance(associations, list):
        raise ValueError("associations must be a list.")

    # Only explicit support links and recorded association links count.
    association_support = {}
    for association in associations:
        if not isinstance(association, dict):
            raise ValueError("Each association must be an object.")

        if association.get("relationship") != "support_link_for_review":
            continue

        ids = association.get("observation_ids", [])
        if not isinstance(ids, list):
            continue

        for observation_id in ids:
            if observation_id is not None:
                association_support.setdefault(observation_id, set()).update(
                    other_id for other_id in ids
                    if other_id is not None and other_id != observation_id
                )

    results = []
    seen_ids = set()

    for index, original in enumerate(observations):
        if not isinstance(original, dict):
            raise ValueError(f"Observation {index} must be an object.")

        observation = deepcopy(original)
        observation_id = observation.get("observation_id")

        if observation_id is not None:
            if observation_id in seen_ids:
                raise ValueError("Duplicate observation_id detected.")
            seen_ids.add(observation_id)

        linked_ids = _linked_evidence_ids(
            observation, "supporting_evidence"
        )
        explicit_support_count = len(linked_ids)

        if observation_id is not None:
            explicit_support_count = max(
                explicit_support_count,
                len(association_support.get(observation_id, set())),
            )

        score, factors = _score_observation(
            observation,
            normalized_weights,
            explicit_support_count,
        )

        # Unaligned observations remain eligible for review but cannot
        # receive a timestamp-based anchor position.
        candidate = {
            "anchor_event_id": f"anchor_{observation_id or index}",
            "observation_id": observation_id,
            "evidence_id": observation.get("evidence_id"),
            "evidence_sha256": observation.get("evidence_sha256"),
            "modality": observation.get("modality"),
            "event_type": observation.get("event_type"),
            "description": observation.get("description"),
            "start_time_seconds": observation.get("global_start_seconds"),
            "end_time_seconds": observation.get("global_end_seconds"),
            "source_reference": observation.get("source_reference", {}),
            "review_priority_score": score,
            "score_factors": factors,
            "score_weights": normalized_weights,
            "priority_band": (
                "high" if score >= 70
                else "medium" if score >= minimum_score
                else "low"
            ),
            "candidate_anchor": score >= minimum_score,
            "review_status": "requires_human_review",
            "interpretation_note": (
                "Review-priority score only; not a probability, proof, "
                "or determination of guilt."
            ),
        }

        results.append(candidate)

    results.sort(
        key=lambda item: (
            -item["review_priority_score"],
            item["start_time_seconds"] is None,
            (
                item["start_time_seconds"]
                if item["start_time_seconds"] is not None
                else float("inf")
            ),
        )
    )

    anchors = [item for item in results if item["candidate_anchor"]]

    return {
        "analysis_type": "anchor_event_scoring",
        "observation_count": len(results),
        "candidate_anchor_count": len(anchors),
        "minimum_score": float(minimum_score),
        "score_interpretation": "review priority, not evidential certainty",
        "anchors": anchors,
        "ranked_observations": results,
        "limitations": [
            "Model confidence may be miscalibrated and is not proof.",
            "Timestamp alignment does not establish causation or identity.",
            "Only explicitly recorded support links affect cross-modal support.",
            "Conflicting evidence raises review priority; it does not imply guilt.",
            "All candidates require human review.",
        ],
    }
