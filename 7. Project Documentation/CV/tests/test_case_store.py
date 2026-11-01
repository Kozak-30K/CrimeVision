
import hashlib
import json

import pytest

from app.services.case_store import CaseStore


@pytest.fixture
def store(tmp_path):
    return CaseStore(tmp_path / "test_crimevision.db")


def test_create_and_retrieve_case(store):
    case = store.create_case("Test investigation", "Test description")

    retrieved = store.get_case(case["case_id"])

    assert retrieved["title"] == "Test investigation"
    assert retrieved["description"] == "Test description"
    assert retrieved["status"] == "open"


def test_case_persists_after_reopening_database(tmp_path):
    db_path = tmp_path / "persistent.db"
    first_store = CaseStore(db_path)
    case = first_store.create_case("Persistent case")

    second_store = CaseStore(db_path)

    assert second_store.get_case(case["case_id"])["title"] == "Persistent case"


def test_case_update_and_filtering(store):
    first = store.create_case("First")
    second = store.create_case("Second")

    store.update_case(
        first["case_id"], title="Updated first", status="closed"
    )

    assert store.get_case(first["case_id"])["title"] == "Updated first"
    assert [c["case_id"] for c in store.list_cases("open")] == [
        second["case_id"]
    ]
    assert [c["case_id"] for c in store.list_cases("closed")] == [
        first["case_id"]
    ]


def test_register_evidence_and_verify_hash(store, tmp_path):
    case = store.create_case("Evidence case")
    evidence_file = tmp_path / "sample.txt"
    contents = b"CrimeVision test evidence"
    evidence_file.write_bytes(contents)

    evidence = store.register_evidence(
        case["case_id"],
        evidence_file,
        "text",
        metadata={"source": "test"},
    )

    assert evidence["sha256"] == hashlib.sha256(contents).hexdigest()
    assert evidence["integrity_verified"] is True
    assert evidence["size_bytes"] == len(contents)
    assert evidence["metadata"]["source"] == "test"


def test_evidence_cannot_be_registered_to_missing_case(store, tmp_path):
    evidence_file = tmp_path / "sample.txt"
    evidence_file.write_text("test")

    with pytest.raises(KeyError):
        store.register_evidence(
            "missing_case", evidence_file, "text"
        )


def test_analysis_round_trip(store, tmp_path):
    case = store.create_case("Analysis case")
    evidence_file = tmp_path / "sample.txt"
    evidence_file.write_text("test")
    evidence = store.register_evidence(
        case["case_id"], evidence_file, "text"
    )

    result = {
        "analysis_type": "anchor_event_scoring",
        "anchors": [{"description": "Candidate event"}],
        "requires_human_review": True,
    }
    saved = store.save_analysis(
        case["case_id"],
        "anchor_event_scoring",
        result,
        evidence_id=evidence["evidence_id"],
    )

    reopened = store.get_analysis(saved["result_id"])

    assert reopened["result"] == result
    assert reopened["evidence_id"] == evidence["evidence_id"]


def test_analysis_rejects_evidence_from_another_case(store, tmp_path):
    first = store.create_case("First case")
    second = store.create_case("Second case")
    evidence_file = tmp_path / "sample.txt"
    evidence_file.write_text("test")
    evidence = store.register_evidence(
        first["case_id"], evidence_file, "text"
    )

    with pytest.raises(ValueError):
        store.save_analysis(
            second["case_id"],
            "test_analysis",
            {"ok": True},
            evidence_id=evidence["evidence_id"],
        )


def test_invalid_inputs_are_rejected(store):
    with pytest.raises(ValueError):
        store.create_case("   ")

    with pytest.raises(ValueError):
        store.list_cases("invalid")

    with pytest.raises(KeyError):
        store.update_case("missing_case", title="Updated")


def test_analysis_rejects_non_json_values(store):
    case = store.create_case("JSON validation case")

    with pytest.raises((ValueError, TypeError)):
        store.save_analysis(
            case["case_id"],
            "test_analysis",
            {"invalid_number": float("nan")},
        )
