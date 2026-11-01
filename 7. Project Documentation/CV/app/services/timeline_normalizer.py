

import math
from typing import Any


def _valid_number(value: Any) -> bool:
    """Accept finite numeric timestamps, but reject booleans."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _valid_indices(value: Any) -> list[int]:
    """Keep valid, unique, non-negative transcript segment indices."""
    if not isinstance(value, list):
        return []

    result = []
    for index in value:
        if (
            isinstance(index, int)
            and not isinstance(index, bool)
            and index >= 0
            and index not in result
        ):
            result.append(index)

    return result


def normalize_timeline(
    keyword_result: dict[str, Any],
    semantic_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Combine keyword and semantic findings into a chronological timeline.

    Similar findings remain separate. Shared transcript segment references
    are used only to flag possible duplicates for human review.
    """
    if not isinstance(keyword_result, dict):
        raise ValueError("Keyword result must be a dictionary.")

    if not isinstance(semantic_result, dict):
        raise ValueError("Semantic result must be a dictionary.")

    keyword_hash = keyword_result.get("source_sha256")
    semantic_hash = semantic_result.get("source_sha256")

    if keyword_hash and semantic_hash and keyword_hash != semantic_hash:
        raise ValueError(
            "Source audio hashes differ; findings cannot be combined."
        )

    keyword_events = keyword_result.get("timeline")
    semantic_events = semantic_result.get("events")

    if not isinstance(keyword_events, list):
        raise ValueError("Keyword result must contain a timeline list.")

    if not isinstance(semantic_events, list):
        raise ValueError("Semantic result must contain an events list.")

    timeline = []

    # Preserve rule-based findings.
    for event in keyword_events:
        if not isinstance(event, dict):
            continue

        timestamp = event.get("audio_timestamp")
        if not isinstance(timestamp, dict):
            continue

        start = timestamp.get("start_seconds")
        end = timestamp.get("end_seconds")

        if (
            not _valid_number(start)
            or not _valid_number(end)
            or start < 0
            or end < start
        ):
            continue

        categories = event.get("candidate_categories", [])
        if not isinstance(categories, list) or not all(
            isinstance(item, str) for item in categories
        ):
            categories = ["unclassified_statement"]

        segment_index = event.get("source_segment_index")
        indices = _valid_indices([segment_index])

        timeline.append({
            "event_id": f"keyword_{len(timeline) + 1:03d}",
            "finding_source": "keyword_extraction",
            "speech_timestamps": {
                "start_seconds": start,
                "end_seconds": end,
            },
            "reported_time": None,
            "description": str(event.get("statement", "")),
            "candidate_categories": categories,
            "people_mentioned": [],
            "location": None,
            "evidence_segment_indices": indices,
            "uncertainty_notes": [
                "Keyword-based finding; verify against the original recording."
            ],
            "possible_duplicates": [],
            "review_status": "requires_human_review",
        })

    # Preserve semantic findings and their validated speech timestamps.
    for event in semantic_events:
        if not isinstance(event, dict):
            continue

        timestamps = event.get("speech_timestamps")
        if not isinstance(timestamps, list):
            continue

        valid_timestamps = []
        for timestamp in timestamps:
            if not isinstance(timestamp, dict):
                continue

            start = timestamp.get("start_seconds")
            end = timestamp.get("end_seconds")

            if (
                _valid_number(start)
                and _valid_number(end)
                and start >= 0
                and end >= start
            ):
                valid_timestamps.append({
                    "start_seconds": start,
                    "end_seconds": end,
                })

        if not valid_timestamps:
            continue

        description = event.get("description")
        event_type = event.get("event_type")

        if not isinstance(description, str) or not description.strip():
            continue
        if not isinstance(event_type, str) or not event_type.strip():
            continue

        people = event.get("people_mentioned", [])
        if not isinstance(people, list) or not all(
            isinstance(person, str) for person in people
        ):
            people = []

        uncertainties = event.get("uncertainty_notes", [])
        if not isinstance(uncertainties, list) or not all(
            isinstance(note, str) for note in uncertainties
        ):
            uncertainties = []

        indices = _valid_indices(event.get("evidence_segment_indices"))

        timeline.append({
            "event_id": f"semantic_{len(timeline) + 1:03d}",
            "finding_source": "semantic_extraction",
            "speech_timestamps": {
                "start_seconds": min(
                    item["start_seconds"] for item in valid_timestamps
                ),
                "end_seconds": max(
                    item["end_seconds"] for item in valid_timestamps
                ),
            },
            "reported_time": event.get("reported_time"),
            "description": description.strip(),
            "candidate_categories": [event_type.strip()],
            "people_mentioned": people,
            "location": event.get("location"),
            "evidence_segment_indices": indices,
            "uncertainty_notes": uncertainties,
            "possible_duplicates": [],
            "review_status": "requires_human_review",
        })

    # Sort by speech time, never by the reported real-world event time.
    timeline.sort(
        key=lambda item: item["speech_timestamps"]["start_seconds"]
    )

    # Shared transcript segments suggest a possible overlap, not proof
    # that two findings describe the same event.
    for i, first in enumerate(timeline):
        first_indices = set(first["evidence_segment_indices"])
        if not first_indices:
            continue

        for second in timeline[i + 1:]:
            if first["finding_source"] == second["finding_source"]:
                continue

            shared = first_indices.intersection(
                second["evidence_segment_indices"]
            )

            if shared:
                first["possible_duplicates"].append({
                    "event_id": second["event_id"],
                    "reason": "Shared transcript segment reference",
                    "shared_segment_indices": sorted(shared),
                })
                second["possible_duplicates"].append({
                    "event_id": first["event_id"],
                    "reason": "Shared transcript segment reference",
                    "shared_segment_indices": sorted(shared),
                })

    return {
        "analysis_type": "unified_forensic_timeline",
        "source_audio": (
            keyword_result.get("source_audio")
            or semantic_result.get("source_audio")
        ),
        "source_sha256": keyword_hash or semantic_hash,
        "timeline_count": len(timeline),
        "timeline": timeline,
        "limitations": [
            "Findings from separate extractors remain separate.",
            "Shared transcript references flag possible overlap, not confirmed duplication.",
            "Speech timestamps indicate when words were spoken, not when the described event occurred.",
            "Reported event times may be missing, inaccurate, or disputed.",
            "Only findings with usable timestamps and required fields are included.",
            "All findings require human review against the original evidence.",
        ],
    }
