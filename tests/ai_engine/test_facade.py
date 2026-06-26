"""C-014 - AI engine facade."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import pytest

from core.ai_engine import AIEngine, AIEngineError, generate_criteria, score_jobs
from core.models.job import Job
from core.models.search_criteria import SearchCriteria


def _job(**overrides) -> Job:
    data = {
        "id": "job-1",
        "title": "Python Developer",
        "company": "Acme",
        "url": "https://example.invalid/job-1",
        "source": "mock",
        "description": "Build APIs.",
        "raw": {"html": "<secret>"},
    }
    data.update(overrides)
    return Job(**data)


class FakePromptProvider:
    def __init__(self, handler: Callable[[str], str]) -> None:
        self.handler = handler
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.handler(prompt)


@pytest.mark.asyncio
async def test_generate_criteria_builds_prompt_and_parses_response():
    provider = FakePromptProvider(
        lambda _prompt: json.dumps(
            {
                "titles": ["Python Developer"],
                "keywords": ["python", "api"],
                "exclude_keywords": ["manager"],
                "seniority_levels": ["senior"],
                "locations": ["remote"],
            }
        )
    )
    engine = AIEngine(provider)

    criteria = await engine.generate_criteria("Senior Python developer seeking remote work")

    assert criteria.titles == ("Python Developer",)
    assert criteria.keywords == ("python", "api")
    assert criteria.raw_profile == "Senior Python developer seeking remote work"
    assert provider.prompts == [
        (
            "SYSTEM: You are a career advisor. Given a professional profile, extract a\n"
            "        structured job search criteria object. Respond ONLY with valid JSON.\n"
            "        Schema: { titles: [], keywords: [], exclude_keywords: [],\n"
            "        seniority_levels: [], locations: [] }\n"
            "USER: Senior Python developer seeking remote work"
        )
    ]


@pytest.mark.asyncio
async def test_generate_criteria_raises_clear_error_on_invalid_provider_response():
    engine = AIEngine(FakePromptProvider(lambda _prompt: "not json"))

    with pytest.raises(AIEngineError, match="criteria"):
        await engine.generate_criteria("profile")


@pytest.mark.asyncio
async def test_score_jobs_batches_and_applies_scores_without_mutating_inputs():
    provider = FakePromptProvider(_score_response_for_prompt)
    engine = AIEngine(provider, batch_size=2)
    criteria = SearchCriteria(keywords=("python",))
    jobs = [
        _job(id="job-1"),
        _job(id="job-2", url="https://example.invalid/job-2"),
        _job(id="job-3", url="https://example.invalid/job-3"),
    ]

    scored = await engine.score_jobs(jobs, criteria)

    assert [job.id for job in scored] == ["job-1", "job-2", "job-3"]
    assert [job.score for job in scored] == [81, 82, 83]
    assert [job.match_reason for job in scored] == [
        "Matched job-1",
        "Matched job-2",
        "Matched job-3",
    ]
    assert all(job.red_flags == () for job in scored)
    assert [job.score for job in jobs] == [None, None, None]
    assert scored[0] is not jobs[0]
    assert len(provider.prompts) == 2
    assert all("https://example.invalid" not in prompt for prompt in provider.prompts)
    assert all("<secret>" not in prompt for prompt in provider.prompts)
    assert all('"source"' not in prompt for prompt in provider.prompts)


@pytest.mark.asyncio
async def test_score_jobs_runs_batches_concurrently_under_bound_and_preserves_order():
    """Batches score concurrently (bounded), and results stay in input order (C-073)."""
    live = {"now": 0, "peak": 0}

    async def provider(prompt: str) -> str:
        live["now"] += 1
        live["peak"] = max(live["peak"], live["now"])
        await asyncio.sleep(0.01)  # force batch overlap
        live["now"] -= 1
        return _score_response_for_prompt(prompt)

    engine = AIEngine(provider, batch_size=1, max_concurrency=2)
    criteria = SearchCriteria(keywords=("python",))
    jobs = [_job(id=f"job-{i}", url=f"https://example.invalid/job-{i}") for i in range(1, 7)]

    scored = await engine.score_jobs(jobs, criteria)

    assert [job.id for job in scored] == [f"job-{i}" for i in range(1, 7)]
    assert [job.score for job in scored] == [80 + i for i in range(1, 7)]
    assert live["peak"] == 2  # saturated the bound, never exceeded it


@pytest.mark.asyncio
async def test_score_jobs_empty_input_returns_empty_without_provider_call():
    provider = FakePromptProvider(lambda _prompt: "[]")
    engine = AIEngine(provider)

    assert await engine.score_jobs([], SearchCriteria()) == []
    assert provider.prompts == []


@pytest.mark.asyncio
async def test_score_jobs_raises_clear_error_on_invalid_batch_response():
    engine = AIEngine(FakePromptProvider(lambda _prompt: "{}"))

    with pytest.raises(AIEngineError, match="score"):
        await engine.score_jobs([_job()], SearchCriteria())


@pytest.mark.asyncio
async def test_module_level_wrappers_delegate_to_facade():
    async def provider(prompt: str) -> str:
        if prompt.startswith("SYSTEM: You are a career advisor."):
            return '{"titles":["Developer"]}'
        return _score_response_for_prompt(prompt)

    criteria = await generate_criteria("profile", provider)
    scored = await score_jobs([_job()], criteria, provider)

    assert criteria.titles == ("Developer",)
    assert scored[0].score == 81


def _score_response_for_prompt(prompt: str) -> str:
    jobs = json.loads(_extract_json_line(prompt, "      JOBS: "))
    return json.dumps(
        [
            {
                "id": job["id"],
                "score": 80 + int(job["id"].removeprefix("job-")),
                "match_reason": f"Matched {job['id']}",
                "red_flags": [],
            }
            for job in jobs
        ]
    )


def _extract_json_line(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing line starting with {prefix!r}")
