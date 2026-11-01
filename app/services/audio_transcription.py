from pathlib import Path
import hashlib

import whisper


MODEL_NAME = "base"
SUPPORTED_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"
}

SUPPORTED_LANGUAGES = {"en", "hi", "te", "fr"}


class AudioTranscriptionService:
    """CPU-based multilingual transcription with source integrity metadata."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.model = whisper.load_model(model_name, device="cpu")

    def transcribe_audio(
        self,
        audio_path: str | Path,
        language: str | None = None,
    ) -> dict:
        audio_path = Path(audio_path).expanduser().resolve()

        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if audio_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported audio extension: {audio_path.suffix}"
            )

        if language is not None:
            language = language.strip().lower()
            if language not in SUPPORTED_LANGUAGES:
                raise ValueError(
                    "Unsupported language. Use en, hi, te, or fr, "
                    "or omit language for automatic detection."
                )

        # Hash the original bytes without modifying the evidence.
        sha256 = hashlib.sha256()
        with audio_path.open("rb") as audio_file:
            for chunk in iter(
                lambda: audio_file.read(1024 * 1024), b""
            ):
                sha256.update(chunk)

        # Whisper decodes and resamples audio to its expected
        # 16 kHz representation internally.
        result = self.model.transcribe(
            str(audio_path),
            language=language,
            task="transcribe",
            fp16=False,
            verbose=False,
        )

        segments = [
            {
                "start": round(float(segment["start"]), 3),
                "end": round(float(segment["end"]), 3),
                "text": segment["text"].strip(),
            }
            for segment in result.get("segments", [])
        ]

        duration = max(
            (segment["end"] for segment in segments),
            default=0.0,
        )

        return {
            "analysis_type": "audio_transcription",
            "source_audio": audio_path.name,
            "source_sha256": sha256.hexdigest(),
            "model": self.model_name,
            "device": "cpu",
            "sample_rate_hz": 16000,
            "language": result.get("language"),
            "duration_seconds": round(duration, 3),
            "segments": segments,
            "transcript": result.get("text", "").strip(),
            "limitations": [
                "Speech recognition may contain transcription errors.",
                "Timestamps locate speech, not necessarily the events described.",
                "The transcript is not a verified witness statement.",
                "Language support does not guarantee equal accuracy across languages.",
            ],
        }