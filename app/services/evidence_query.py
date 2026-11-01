"""Case-scoped, evidence-grounded search over saved CrimeVision analyses.

This module performs deterministic lexical search. It does not generate
conclusions or treat candidate findings as verified real-world events.
"""
from __future__ import annotations

import re
from typing import Any


_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "did", "do",
    "does", "for", "from", "had", "has", "have", "he", "her", "him", "his",
    "i", "in", "into", "is", "it", "its", "me", "of", "on", "or", "our",
    "she", "that", "the", "their", "them", "there", "they", "this", "to",
    "was", "we", "were", "what", "when", "where", "which", "who", "with",
    "you", "your", "evidence", "show", "find", "tell", "about", "mention",
    "mentions", "mentioned",
}

_TEXT_KEYS = {
    "description", "statement", "text", "transcript", "content", "caption",
    "event_type", "category", "candidate_categories", "people_mentioned",
    "location", "reported_time", "relationship", "interpretation_note",
    "name", "summary",
}

_TIME_KEYS = {
    "start_seconds", "end_seconds", "start_time_seconds", "end_time_seconds",
    "global_start_seconds", "global_end_seconds", "audio_timestamp",
    "speech_timestamps", "timestamp", "reported_time",
}


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[a-z0-9]+", query.casefold())
    return [term for term in terms if term not in _STOP_WORDS and len(term) > 1]


def _walk(value: Any, path: str = "$"):
    """Yield (path, value) pairs from a JSON-like result."""
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _text_for_search(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_text_for_search(item) for item in value)
    if isinstance(value, dict):
        return " ".join(
            _text_for_search(child)
            for key, child in value.items()
            if key in _TEXT_KEYS
        )
    return ""


def _context_for_match(result: dict[str, Any], match_path: str) -> dict[str, Any]:
    """Collect provenance identifiers and time fields from the containing result."""
    evidence_ids: set[str] = set()
    observation_ids: set[str] = set()
    timestamps: list[dict[str, Any]] = []

    for _, item in _walk(result):
        if not isinstance(item, dict):
            continue
        evidence_id = item.get("evidence_id")
        if isinstance(evidence_id, str) and evidence_id:
            evidence_ids.add(evidence_id)
        observation_id = item.get("observation_id")
        if isinstance(observation_id, str) and observation_id:
            observation_ids.add(observation_id)

        # Keep timestamp structures as found; do not infer or fabricate times.
        for key in ("audio_timestamp", "speech_timestamps"):
            stamp = item.get(key)
            if isinstance(stamp, dict):
                timestamps.append(dict(stamp))
            elif isinstance(stamp, list):
                timestamps.extend(dict(x) for x in stamp if isinstance(x, dict))

        time_fields = {
            key: item[key]
            for key in _TIME_KEYS
            if key in item and not isinstance(item[key], (dict, list))
        }
        if time_fields:
            timestamps.append(time_fields)

    return {
        "evidence_ids": sorted(evidence_ids),
        "observation_ids": sorted(observation_ids),
        "timestamps": timestamps,
    }


def query_case(
    store,
    case_id: str,
    query: str,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    """Search saved analyses for one case and return traceable text matches.

    `store` must provide `get_case(case_id)` and `list_analyses(case_id)`,
    as implemented by `app.services.case_store.CaseStore`.
    """
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string.")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    case = store.get_case(case_id)
    if case is None:
        raise KeyError(f"Case not found: {case_id}")

    terms = _query_terms(query)
    if not terms:
        raise ValueError("Query must contain at least one searchable term.")

    matches = []
    analyses = store.list_analyses(case_id)

    for analysis in analyses:
        result = analysis.get("result")
        if not isinstance(result, dict):
            continue

        # Search leaf text values and list/dict fields commonly used for findings.
        for path, value in _walk(result):
            if not isinstance(value, str) or not value.strip():
                continue

            parent_key = path.rsplit(".", 1)[-1].split("[", 1)[0]
            if parent_key not in _TEXT_KEYS:
                continue

            normalized = value.casefold()
            matched_terms = [term for term in terms if term in normalized]
            unique_terms = set(terms)
            # Require every meaningful query term in the same text span to
            # avoid weak matches caused by common words across unrelated findings.
            if not unique_terms.issubset(set(matched_terms)):
                continue

            score = 1.0
            matches.append({
                "analysis_id": analysis["result_id"],
                "analysis_type": analysis["analysis_type"],
                "analysis_created_at_utc": analysis.get("created_at_utc"),
                "analysis_evidence_id": analysis.get("evidence_id"),
                "match_path": path,
                "matched_text": value.strip(),
                "matched_terms": sorted(set(matched_terms)),
                "match_score": round(score, 3),
                **_context_for_match(result, path),
                "review_status": "requires_human_review",
                "interpretation_note": (
                    "Text match in a saved analysis. This does not verify that "
                    "the described real-world event occurred."
                ),
            })

    matches.sort(
        key=lambda item: (
            -item["match_score"],
            item["analysis_created_at_utc"] or "",
            item["analysis_id"],
            item["match_path"],
        )
    )
    matches = matches[:limit]

    return {
        "query": query,
        "case_id": case_id,
        "analysis_count_searched": len(analyses),
        "match_count": len(matches),
        "matches": matches,
        "search_method": "deterministic_lexical",
        "limitations": [
            "Only saved analysis results in this case are searched.",
            "Lexical matching may miss synonyms, paraphrases, and misspellings.",
            "A match is not independent verification of a described event.",
            "Source timestamps are reported as stored; they are not reinterpreted.",
            "Matches require human review against the original evidence.",
        ],
    }
