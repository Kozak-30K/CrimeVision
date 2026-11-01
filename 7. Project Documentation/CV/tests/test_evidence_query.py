import pytest

from app.services.case_store import CaseStore
from app.services.evidence_query import query_case


@pytest.fixture
def store(tmp_path):
    return CaseStore(tmp_path / "crimevision_query_test.db")


def test_query_finds_saved_text_with_provenance(store):
    case = store.create_case("Query test")
    evidence = store.save_analysis(
        case["case_id"],
        "unified_forensic_timeline",
        {
            "analysis_type": "unified_forensic_timeline",
            "timeline": [
                {
                    "event_id": "semantic_001",
                    "description": "A person entered the building.",
                    "speech_timestamps": {
                        "start_seconds": 4.2,
                        "end_seconds": 5.1,
                    },
                    "review_status": "requires_human_review",
                }
            ],
        },
    )

    result = query_case(
        store, case["case_id"], "entered building"
    )

    assert result["analysis_count_searched"] == 1
    assert result["match_count"] >= 1
    match = next(
        item for item in result["matches"]
        if "entered the building" in item["matched_text"]
    )
    assert match["analysis_id"] == evidence["result_id"]
    assert match["analysis_type"] == "unified_forensic_timeline"
    assert match["review_status"] == "requires_human_review"
    assert match["timestamps"]


def test_query_is_case_scoped(store):
    first = store.create_case("First")
    second = store.create_case("Second")
    store.save_analysis(
        first["case_id"], "test", {"description": "red vehicle outside"}
    )
    store.save_analysis(
        second["case_id"], "test", {"description": "blue vehicle inside"}
    )

    result = query_case(store, first["case_id"], "blue vehicle")

    assert result["match_count"] == 0


def test_query_rejects_missing_case_and_invalid_inputs(store):
    with pytest.raises(KeyError):
        query_case(store, "missing", "building")

    case = store.create_case("Validation")
    with pytest.raises(ValueError):
        query_case(store, case["case_id"], "   ")
    with pytest.raises(ValueError):
        query_case(store, case["case_id"], "building", limit=0)


def test_query_reports_no_matches_without_inventing_findings(store):
    case = store.create_case("Empty case")
    result = query_case(store, case["case_id"], "weapon")

    assert result["match_count"] == 0
    assert result["matches"] == []
    assert result["search_method"] == "deterministic_lexical"
