"""Shared evidence and observation schemas for CrimeVision."""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import uuid


SCHEMA_VERSION = "1.0"


def sha256_file(file_path: str | Path) -> str:
    """Calculate the SHA-256 hash of the original evidence file."""
    digest = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def create_evidence_record(
    file_path: str | Path,
    modality: str,
    evidence_id: str | None = None,
    source_sha256: str | None = None,
) -> dict:
    """Create a common evidence record without modifying the source file."""
    path = Path(file_path).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(f"Evidence file not found: {path}")

    if modality not in {"image", "audio", "video", "text"}:
        raise ValueError("Unsupported evidence modality.")

    actual_hash = sha256_file(path)

    if source_sha256 and source_sha256.lower() != actual_hash:
        raise ValueError("Evidence hash does not match the source file.")

    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": evidence_id or f"ev_{uuid.uuid4().hex}",
        "filename": path.name,
        "modality": modality,
        "sha256": actual_hash,
        "size_bytes": path.stat().st_size,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "integrity_verified": True,
    }


def create_observation(
    evidence_id: str,
    evidence_sha256: str,
    modality: str,
    event_type: str,
    description: str,
    start_time_seconds: float | None = None,
    end_time_seconds: float | None = None,
    source_reference: dict | None = None,
    confidence: float | None = None,
    model_name: str | None = None,
    supporting_evidence: list | None = None,
    conflicting_evidence: list | None = None,
) -> dict:
    """Create a standardized, reviewable observation."""
    if modality not in {"image", "audio", "video", "text"}:
        raise ValueError("Unsupported observation modality.")

    if start_time_seconds is not None and start_time_seconds < 0:
        raise ValueError("Start time cannot be negative.")

    if end_time_seconds is not None and end_time_seconds < 0:
        raise ValueError("End time cannot be negative.")

    if (
        start_time_seconds is not None
        and end_time_seconds is not None
        and end_time_seconds < start_time_seconds
    ):
        raise ValueError("End time cannot precede start time.")

    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError("Confidence must be between 0 and 1.")

    return {
        "observation_id": f"obs_{uuid.uuid4().hex}",
        "evidence_id": evidence_id,
        "evidence_sha256": evidence_sha256,
        "modality": modality,
        "event_type": event_type,
        "description": description,
        "start_time_seconds": start_time_seconds,
        "end_time_seconds": end_time_seconds,
        "source_reference": source_reference or {},
        "confidence": confidence,
        "model_name": model_name,
        "supporting_evidence": supporting_evidence or [],
        "conflicting_evidence": conflicting_evidence or [],
        "review_status": "requires_human_review",
        "schema_version": SCHEMA_VERSION,
    }
