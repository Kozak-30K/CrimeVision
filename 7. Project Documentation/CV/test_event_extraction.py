
from app.services.event_extraction import extract_events


sample_transcription = {
    "analysis_type": "audio_transcription",
    "source_audio": "sample.wav",
    "source_sha256": "example_hash",
    "model": "tiny",
    "device": "cpu",
    "language": "en",
    "segments": [
        {
            "start": 0.0,
            "end": 3.5,
            "text": "I heard someone shouting for help.",
        },
        {
            "start": 3.5,
            "end": 7.0,
            "text": "A person ran out of the building.",
        },
    ],
}

result = extract_events(sample_transcription)

assert result["event_count"] == 2
assert result["timeline"][0]["audio_timestamp"]["start_seconds"] == 0.0
assert "speech_or_communication" in (
    result["timeline"][0]["candidate_categories"]
)
assert "movement" in result["timeline"][1]["candidate_categories"]
assert all(
    event["review_status"] == "requires_human_review"
    for event in result["timeline"]
)

print("Event extraction PASS")
print(f"Events extracted: {result['event_count']}")

for event in result["timeline"]:
    timestamp = event["audio_timestamp"]
    print(
        f"[{timestamp['start_seconds']:.1f}s - "
        f"{timestamp['end_seconds']:.1f}s] "
        f"{event['candidate_categories']}: {event['statement']}"
    )
