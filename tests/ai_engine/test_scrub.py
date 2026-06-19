"""C-012 - pure job field stripping for AI payloads."""
from __future__ import annotations

import json
from datetime import datetime

from core.ai_engine.prompts import build_score_jobs_prompt
from core.ai_engine.scrub import strip_job_for_ai, strip_jobs_for_ai
from core.models.job import Job
from core.models.search_criteria import SearchCriteria


def _job(**overrides):
    data = {
        "id": "job-1",
        "title": "Python Developer",
        "company": "Acme",
        "url": "https://example.invalid/job-1",
        "source": "mock",
        "location": "Remote",
        "description": "Build APIs.",
        "salary_range": "$1",
        "posted_date": datetime(2026, 6, 19),
        "score": 99,
        "match_reason": "old score",
        "red_flags": ("old",),
        "raw": {"html": "<secret>"},
    }
    data.update(overrides)
    return Job(**data)


def test_strip_job_for_ai_keeps_only_sdd_fields():
    payload = strip_job_for_ai(_job())

    assert payload == {
        "id": "job-1",
        "title": "Python Developer",
        "company": "Acme",
        "description": "Build APIs.",
    }


def test_strip_job_for_ai_preserves_none_description():
    payload = strip_job_for_ai(_job(description=None))

    assert payload == {
        "id": "job-1",
        "title": "Python Developer",
        "company": "Acme",
        "description": None,
    }


def test_strip_jobs_for_ai_is_order_preserving_and_pure():
    first = _job(id="job-1")
    second = _job(id="job-2", url="https://example.invalid/job-2")

    payloads = strip_jobs_for_ai([first, second])

    assert [payload["id"] for payload in payloads] == ["job-1", "job-2"]
    assert first.raw == {"html": "<secret>"}
    assert second.url == "https://example.invalid/job-2"


def test_score_prompt_uses_stripped_job_payloads():
    prompt = build_score_jobs_prompt(SearchCriteria(), [_job()])
    jobs_line = next(line for line in prompt.splitlines() if line.startswith("      JOBS: "))
    jobs = json.loads(jobs_line.removeprefix("      JOBS: "))

    assert jobs == [
        {
            "id": "job-1",
            "title": "Python Developer",
            "company": "Acme",
            "description": "Build APIs.",
        }
    ]
    assert "https://example.invalid" not in prompt
    assert "<secret>" not in prompt
    assert "salary_range" not in prompt
