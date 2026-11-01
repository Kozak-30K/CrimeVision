
"""File-integrity verification for registered CrimeVision evidence.

Verifies a file against the SHA-256 digest and size recorded at registration.
This does not establish authenticity or history before registration.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.forensic_schema import sha256_file


def verify_evidence_integrity(
    store,
    case_id: str,
    evidence_id: str,
    file_path: str | Path,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """Compare a file with its registered evidence record.

    Missing files produce a failed report rather than raising
    FileNotFoundError. Reports are saved by default.
    """
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string.")
    if not isinstance(evidence_id, str) or not evidence_id.strip():
        raise ValueError("evidence_id must be a non-empty string.")

    case = store.get_case(case_id)
    if case is None:
        raise KeyError(f"Case not found: {case_id}")

    evidence = store.get_evidence(evidence_id)
    if evidence is None or evidence.get("case_id") != case_id:
        raise ValueError("evidence_id must belong to the specified case.")

    path = Path(file_path).expanduser()
    checked_at = datetime.now(timezone.utc).isoformat()
    expected_hash = evidence["sha256"]
    expected_size = evidence["size_bytes"]

    report: dict[str, Any] = {
        "analysis_type": "evidence_integrity_verification",
        "case_id": case_id,
        "evidence_id": evidence_id,
        "checked_at_utc": checked_at,
        "file_path": str(path.resolve()),
        "expected_sha256": expected_hash,
        "expected_size_bytes": expected_size,
        "actual_sha256": None,
        "actual_size_bytes": None,
        "status": "verification_failed",
        "checks": {
            "file_exists": False,
            "sha256_matches": False,
            "size_matches": False,
        },
        "findings": [],
        "requires_human_review": True,
        "limitations": [
            "A matching hash shows that the checked file matches the digest stored at registration.",
            "It does not prove who created the file or whether it was altered before registration.",
            "This report is not a complete chain-of-custody record.",
            "Verify that the supplied path is the intended original evidence file.",
        ],
    }

    if not path.is_file():
        report["findings"].append(
            "The supplied evidence file is missing or is not a regular file."
        )
    else:
        report["checks"]["file_exists"] = True
        report["actual_size_bytes"] = path.stat().st_size
        report["actual_sha256"] = sha256_file(path)

        report["checks"]["sha256_matches"] = (
            report["actual_sha256"] == expected_hash
        )
        report["checks"]["size_matches"] = (
            report["actual_size_bytes"] == expected_size
        )

        if not report["checks"]["sha256_matches"]:
            report["findings"].append(
                "SHA-256 mismatch: file contents differ from the registered digest."
            )

        if not report["checks"]["size_matches"]:
            report["findings"].append(
                "File-size mismatch: current size differs from the registered size."
            )

        if (
            report["checks"]["sha256_matches"]
            and report["checks"]["size_matches"]
        ):
            report["status"] = "verified_match"
            report["findings"].append(
                "Current file matches the registered SHA-256 digest and size."
            )
        else:
            report["status"] = "mismatch"

    if persist:
        saved = store.save_analysis(
            case_id,
            "evidence_integrity_verification",
            report,
            evidence_id=evidence_id,
        )
        report["verification_result_id"] = saved["result_id"]

    return report
