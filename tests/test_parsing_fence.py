"""C-054 — JSON fence stripping in parsing._loads (SDD §5.2)."""
from __future__ import annotations

import json

from core.ai_engine.parsing import (
    _loads,
    parse_criteria_response,
    parse_scored_jobs_response,
)
from core.models.job import Job


def _job(id: str = "j1") -> Job:
    return Job(
        id=id,
        title="Dev",
        company="Acme",
        url=f"https://example.invalid/{id}",
        source="mock",
        description="",
        raw={},
    )


# ---------------------------------------------------------------------------
# _loads unit tests
# ---------------------------------------------------------------------------


def test_loads_bare_json():
    assert _loads('{"a": 1}') == {"a": 1}


def test_loads_json_fence():
    text = "```json\n{\"a\": 1}\n```"
    assert _loads(text) == {"a": 1}


def test_loads_bare_fence():
    text = "```\n{\"a\": 1}\n```"
    assert _loads(text) == {"a": 1}


def test_loads_fence_with_trailing_text():
    # text before/after fence should be ignored — only content inside matters
    text = "Here is the JSON:\n```json\n{\"a\": 1}\n```\nDone."
    assert _loads(text) == {"a": 1}


def test_loads_invalid_returns_none():
    assert _loads("not json at all") is None


def test_loads_fence_with_invalid_json_returns_none():
    text = "```json\nbad content\n```"
    assert _loads(text) is None


def test_loads_empty_string_returns_none():
    assert _loads("") is None


# ---------------------------------------------------------------------------
# End-to-end through parse_criteria_response
# ---------------------------------------------------------------------------


def test_parse_criteria_response_accepts_fenced_input():
    payload = {
        "titles": ["Python Engineer"],
        "keywords": ["python"],
        "exclude_keywords": [],
        "seniority_levels": ["senior"],
        "locations": ["remote"],
    }
    fenced = f"```json\n{json.dumps(payload)}\n```"
    criteria = parse_criteria_response(fenced, raw_profile="test profile")
    assert criteria is not None
    assert criteria.titles == ("Python Engineer",)
    assert criteria.keywords == ("python",)
    assert criteria.raw_profile == "test profile"


# ---------------------------------------------------------------------------
# End-to-end through parse_scored_jobs_response
# ---------------------------------------------------------------------------


def test_parse_scored_jobs_response_accepts_fenced_input():
    job = _job("j1")
    payload = [{"id": "j1", "score": 88, "match_reason": "good", "red_flags": []}]
    fenced = f"```json\n{json.dumps(payload)}\n```"
    result = parse_scored_jobs_response(fenced, [job])
    assert result is not None
    assert result[0].score == 88
    assert result[0].match_reason == "good"
