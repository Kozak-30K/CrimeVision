"""Normalize timestamps and align forensic observations."""

from copy import deepcopy
import math


def synchronize_observations(
    observations: list[dict],
    offsets_seconds: dict[str, float] | None = None,
    shared_time_origin: bool = False,
) -> dict:
    """
    Align observations to a common time origin.

    offsets_seconds maps evidence_id to its verified offset from
    the common origin. An offset must be established externally;
    it is never inferred from matching timestamps.

    shared_time_origin=True means all supplied timestamps already
    use the same recording/session origin.
    """
    if not isinstance(observations, list):
        raise ValueError("observations must be a list.")

    offsets = offsets_seconds or {}
    normalized = []
    unsynchronized_count = 0

    for index, original in enumerate(observations):
        if not isinstance(original, dict):
            raise ValueError(f"Observation {index} must be an object.")

        item = deepcopy(original)
        evidence_id = item.get("evidence_id")

        start = item.get("start_time_seconds")
        end = item.get("end_time_seconds")

        for field, value in (("start", start), ("end", end)):
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(
                        f"Observation {index} has invalid {field} timestamp."
                    )
                if value < 0:
                    raise ValueError(
                        f"Observation {index} has a negative {field} timestamp."
                    )

        if start is not None and end is not None and end < start:
            raise ValueError(
                f"Observation {index} ends before it starts."
            )

        offset = None

        if shared_time_origin:
            offset = 0.0
        elif evidence_id in offsets:
            offset = offsets[evidence_id]

            if (
                isinstance(offset, bool)
                or not isinstance(offset, (int, float))
                or not math.isfinite(offset)
            ):
                raise ValueError(
                    f"Invalid verified offset for evidence {evidence_id}."
                )

        if offset is not None:
            if start is not None:
                item["global_start_seconds"] = round(start + offset, 3)
            else:
                item["global_start_seconds"] = None

            if end is not None:
                item["global_end_seconds"] = round(end + offset, 3)
            else:
                item["global_end_seconds"] = None

            item["synchronization_status"] = "aligned"
            item["applied_offset_seconds"] = float(offset)
        else:
            item["global_start_seconds"] = None
            item["global_end_seconds"] = None
            item["synchronization_status"] = "unverified"
            item["applied_offset_seconds"] = None
            unsynchronized_count += 1

        normalized.append(item)

    # Aligned observations are chronologically ordered first.
    # Unaligned observations remain present and are not falsely
    # positioned on the shared timeline.
    normalized.sort(
        key=lambda item: (
            item["global_start_seconds"] is None,
            (
                item["global_start_seconds"]
                if item["global_start_seconds"] is not None
                else float("inf")
            ),
        )
    )

    return {
        "analysis_type": "temporal_synchronization",
        "shared_time_origin": shared_time_origin,
        "observation_count": len(normalized),
        "aligned_count": len(normalized) - unsynchronized_count,
        "unsynchronized_count": unsynchronized_count,
        "timeline": normalized,
        "limitations": [
            "Offsets must come from verified recording/session timing.",
            "Matching timestamps alone do not prove events are related.",
            "Unaligned observations are retained without inventing a global time.",
        ],
    }
