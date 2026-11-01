
import re
from typing import Any


# These patterns identify possible event-related statements.
# They do not establish that the described event actually occurred.
EVENT_PATTERNS = {
    "violence_or_threat": re.compile(
        r"\b(hit|attacked|attacking|shot|shooting|stabbed|"
        r"threatened|threatening|assaulted|fought|fight)\b",
        re.IGNORECASE,
    ),
    "movement": re.compile(
        r"\b(ran|running|entered|exited|left|arrived|"
        r"came in|went out|escaped|chased|followed)\b",
        re.IGNORECASE,
    ),
    "theft_or_property": re.compile(
        r"\b(stole|stolen|took|robbed|robbery|theft|"
        r"missing|broke|damaged)\b",
        re.IGNORECASE,
    ),
    "speech_or_communication": re.compile(
        r"\b(said|told|asked|called|shouted|screamed|"
        r"heard|reported|warned|claimed)\b",
        re.IGNORECASE,
    ),
    "emergency_or_response": re.compile(
        r"\b(police|ambulance|emergency|help|911|112|"
        r"hospital|firefighters)\b",
        re.IGNORECASE,
    ),
    "time_reference": re.compile(
        r"\b(yesterday|today|tonight|this morning|"
        r"last night|at \d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
        re.IGNORECASE,
    ),
}


def classify_statement(text: str) -> list[str]:
    """Return candidate categories based on words in a transcript segment."""
    categories = [
        category
        for category, pattern in EVENT_PATTERNS.items()
        if pattern.search(text)
    ]
    return categories or ["unclassified_statement"]


def extract_events(transcription: dict[str, Any]) -> dict[str, Any]:
    """
    Convert Whisper segments into a timestamped, reviewable event timeline.

    Audio segment timestamps indicate when speech occurred, not necessarily
    when the described real-world event occurred.
    """
    if not isinstance(transcription, dict):
        raise ValueError("Transcription must be a dictionary.")

    segments = transcription.get("segments")
    if not isinstance(segments, list):
        raise ValueError("Transcription must contain a segments list.")

    events = []

    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue

        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        start = segment.get("start")
        end = segment.get("end")

        try:
            start = float(start)
            end = float(end)
        except (TypeError, ValueError):
            raise ValueError(
                f"Segment {index} has invalid start or end timestamps."
            )

        if start < 0 or end < start:
            raise ValueError(
                f"Segment {index} has inconsistent timestamps."
            )

        events.append({
            "event_id": f"audio_event_{len(events) + 1:03d}",
            "audio_timestamp": {
                "start_seconds": start,
                "end_seconds": end,
            },
            "statement": text,
            "candidate_categories": classify_statement(text),
            "source_segment_index": index - 1,
            "review_status": "requires_human_review",
            "interpretation_note": (
                "This is a transcript-derived statement, not a verified "
                "real-world event. Audio timestamps locate the speech only."
            ),
        })

    return {
        "analysis_type": "audio_event_extraction",
        "source_audio": transcription.get("source_audio"),
        "source_sha256": transcription.get("source_sha256"),
        "model": transcription.get("model"),
        "device": transcription.get("device"),
        "language": transcription.get("language"),
        "event_count": len(events),
        "timeline": sorted(
            events,
            key=lambda event: event["audio_timestamp"]["start_seconds"],
        ),
        "limitations": [
            "Events are candidate categories inferred from transcript wording.",
            "Audio timestamps indicate when words were spoken, not when a described event occurred.",
            "Transcription errors can affect event extraction.",
            "All candidate events require human review against the original recording.",
        ],
    }
