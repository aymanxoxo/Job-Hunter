"""Reusable AI-provider contract checks (SDD §12).

Every provider — built-in or user drop-in — must generate a ``SearchCriteria`` and return scored
``Job`` instances. This helper is applied by per-provider tests and, once plugin discovery (C-009)
exists, parametrised over all discovered providers.
"""
from __future__ import annotations

from core.ai_providers.base_provider import BaseAIProvider
from core.models.job import Job
from core.models.search_criteria import SearchCriteria


async def assert_provider_generates_valid_criteria(
    provider: BaseAIProvider, profile: str
) -> None:
    """Run ``provider.generate_criteria`` and assert it returns ``SearchCriteria``."""
    criteria = await provider.generate_criteria(profile)
    assert isinstance(criteria, SearchCriteria)


async def assert_provider_scores_valid_jobs(
    provider: BaseAIProvider, jobs: list[Job], criteria: SearchCriteria
) -> None:
    """Run ``provider.score_jobs`` and assert the returned scores meet the provider contract."""
    scored = await provider.score_jobs(jobs, criteria)
    assert isinstance(scored, list)
    assert [job.id for job in scored] == [job.id for job in jobs]
    for job in scored:
        assert isinstance(job, Job), f"{provider.name} returned a non-Job: {type(job).__name__}"
        assert job.score is not None
