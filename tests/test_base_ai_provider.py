"""C-006 — BaseAIProvider ABC contract (SDD §4.2)."""
import types

import pytest

from core.ai_providers import BaseAIProvider
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from tests.contracts.provider_contract import (
    assert_provider_generates_valid_criteria,
    assert_provider_scores_valid_jobs,
)


class _DummyProvider(BaseAIProvider):
    name = "dummy-ai"

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        return SearchCriteria(raw_profile=profile, keywords=("python",))

    async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
        return [
            job.model_copy(
                update={
                    "score": 90,
                    "match_reason": "Strong keyword match",
                    "red_flags": ("none",),
                }
            )
            for job in jobs
        ]


def _job(**overrides):
    base = dict(id="1", title="Python Dev", company="Acme", url="https://x", source="mock")
    base.update(overrides)
    return Job(**base)


def test_base_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseAIProvider()


def test_subclass_without_generate_criteria_is_abstract():
    class NoGenerate(BaseAIProvider):
        async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
            return jobs

    with pytest.raises(TypeError):
        NoGenerate()


def test_subclass_without_score_jobs_is_abstract():
    class NoScore(BaseAIProvider):
        async def generate_criteria(self, profile: str) -> SearchCriteria:
            return SearchCriteria(raw_profile=profile)

    with pytest.raises(TypeError):
        NoScore()


def test_defaults():
    provider = _DummyProvider()
    assert provider.name == "dummy-ai"
    assert provider.auth_methods == ("api_key",)
    assert provider.supports_local is False


async def test_initialize_defaults_to_none():
    assert await _DummyProvider().initialize() is None


async def test_generate_criteria_meets_provider_contract():
    provider = _DummyProvider()
    await assert_provider_generates_valid_criteria(provider, "Senior Python developer")
    criteria = await provider.generate_criteria("Senior Python developer")
    assert criteria.raw_profile == "Senior Python developer"
    assert criteria.keywords == ("python",)


async def test_score_jobs_meets_provider_contract_and_does_not_mutate_inputs():
    provider = _DummyProvider()
    original = _job()
    await assert_provider_scores_valid_jobs(provider, [original], SearchCriteria())
    scored = await provider.score_jobs([original], SearchCriteria())
    assert scored[0].score == 90
    assert scored[0].match_reason == "Strong keyword match"
    assert scored[0].red_flags == ("none",)
    assert original.score is None


async def test_contract_helper_rejects_non_job_scored_items():
    """A duck-typed object with the right fields must NOT pass the contract (it is not a Job)."""

    class _DuckProvider(BaseAIProvider):
        name = "duck-ai"

        async def generate_criteria(self, profile: str) -> SearchCriteria:
            return SearchCriteria(raw_profile=profile)

        async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list:
            return [types.SimpleNamespace(id=jobs[0].id, score=90)]

    with pytest.raises(AssertionError):
        await assert_provider_scores_valid_jobs(_DuckProvider(), [_job()], SearchCriteria())
