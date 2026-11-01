
import hashlib

import pytest

from app.services.case_store import CaseStore
from app.services.evidence_integrity import verify_evidence_integrity


@pytest.fixture
def setup_case(tmp_path):
    store = CaseStore(tmp_path / "integrity.db")
    case = store.create_case("Integrity test")

    source = tmp_path / "evidence.txt"
    source.write_bytes(b"original evidence")

    evidence = store.register_evidence(
        case["case_id"], source, "text"
    )

    return store, case, source, evidence


def test_matching_file_passes_hash_and_size_checks(setup_case):
    store, case, source, evidence = setup_case

    report = verify_evidence_integrity(
        store, case["case_id"], evidence["evidence_id"], source
    )

    assert report["status"] == "verified_match"
    assert report["actual_sha256"] == hashlib.sha256(
        b"original evidence"
    ).hexdigest()

    assert report["checks"] == {
        "file_exists": True,
        "sha256_matches": True,
        "size_matches": True,
    }

    assert report["verification_result_id"]

    saved = store.get_analysis(report["verification_result_id"])
    assert saved["analysis_type"] == "evidence_integrity_verification"
    assert saved["evidence_id"] == evidence["evidence_id"]


def test_modified_file_fails_verification(setup_case):
    store, case, source, evidence = setup_case
    source.write_bytes(b"modified evidence")

    report = verify_evidence_integrity(
        store,
        case["case_id"],
        evidence["evidence_id"],
        source,
        persist=False,
    )

    assert report["status"] == "mismatch"
    assert report["checks"]["sha256_matches"] is False
    # The modified content has a different hash but the same byte length.
    assert report["checks"]["size_matches"] is True


def test_missing_file_is_reported_not_raised(setup_case, tmp_path):
    store, case, source, evidence = setup_case

    report = verify_evidence_integrity(
        store,
        case["case_id"],
        evidence["evidence_id"],
        tmp_path / "missing.txt",
        persist=False,
    )

    assert report["status"] == "verification_failed"
    assert report["checks"]["file_exists"] is False
    assert report["actual_sha256"] is None


def test_evidence_must_belong_to_requested_case(setup_case):
    store, case, source, evidence = setup_case
    other_case = store.create_case("Other case")

    with pytest.raises(ValueError, match="belong"):
        verify_evidence_integrity(
            store,
            other_case["case_id"],
            evidence["evidence_id"],
            source,
            persist=False,
        )


def test_unknown_case_is_rejected(setup_case):
    store, case, source, evidence = setup_case

    with pytest.raises(KeyError):
        verify_evidence_integrity(
            store,
            "missing",
            evidence["evidence_id"],
            source,
            persist=False,
        )
