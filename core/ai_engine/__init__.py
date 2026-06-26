"""AI engine facade and pure helper exports."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from core.ai_engine.batching import batch_items
from core.ai_engine.parsing import parse_criteria_response, parse_scored_jobs_response
from core.ai_engine.prompts import build_generate_criteria_prompt, build_score_jobs_prompt
from core.ai_engine.scrub import strip_job_for_ai, strip_jobs_for_ai
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

ProviderCall = Callable[[str], Awaitable[str]]


class AIEngineError(RuntimeError):
    """Raised when provider output cannot be recovered into an engine result."""


# Default ceiling on concurrent scoring batches in flight, so a large job set cannot fan
# out into an unbounded number of simultaneous provider calls (C-073).
_DEFAULT_SCORE_CONCURRENCY = 5


@dataclass(frozen=True)
class AIEngine:
    """Async facade that turns provider text responses into JobHunter models."""

    call_provider: ProviderCall
    batch_size: int = 15
    max_concurrency: int = _DEFAULT_SCORE_CONCURRENCY

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        """Generate structured search criteria from a plain-text profile."""
        prompt = build_generate_criteria_prompt(profile)
        response = await self.call_provider(prompt)
        criteria = parse_criteria_response(response, raw_profile=profile)
        if criteria is None:
            raise AIEngineError("Provider returned invalid criteria JSON.")
        return criteria

    async def score_jobs(self, jobs: Sequence[Job], criteria: SearchCriteria) -> list[Job]:
        """Score jobs in batches concurrently (bounded) without mutating the input jobs.

        Batches run under a ``Semaphore(max_concurrency)`` so throughput improves without an
        unbounded provider-call fan-out; ``asyncio.gather`` preserves batch order so results
        come back in the same order as the input jobs.
        """
        batches = list(batch_items(jobs, batch_size=self.batch_size))
        if not batches:
            return []
        semaphore = asyncio.Semaphore(max(1, self.max_concurrency))

        async def _score_batch(batch: list[Job]) -> list[Job]:
            async with semaphore:
                prompt = build_score_jobs_prompt(criteria, batch)
                response = await self.call_provider(prompt)
            scored_batch = parse_scored_jobs_response(response, batch)
            if scored_batch is None:
                raise AIEngineError("Provider returned invalid score JSON.")
            return scored_batch

        scored_jobs: list[Job] = []
        for scored_batch in await asyncio.gather(*(_score_batch(b) for b in batches)):
            scored_jobs.extend(scored_batch)
        return scored_jobs


async def generate_criteria(profile: str, call_provider: ProviderCall) -> SearchCriteria:
    """Generate criteria with a one-off engine facade."""
    return await AIEngine(call_provider).generate_criteria(profile)


async def score_jobs(
    jobs: Sequence[Job],
    criteria: SearchCriteria,
    call_provider: ProviderCall,
    *,
    batch_size: int = 15,
    max_concurrency: int = _DEFAULT_SCORE_CONCURRENCY,
) -> list[Job]:
    """Score jobs with a one-off engine facade."""
    return await AIEngine(
        call_provider, batch_size=batch_size, max_concurrency=max_concurrency
    ).score_jobs(jobs, criteria)

__all__ = [
    "AIEngine",
    "AIEngineError",
    "ProviderCall",
    "batch_items",
    "build_generate_criteria_prompt",
    "build_score_jobs_prompt",
    "generate_criteria",
    "parse_criteria_response",
    "parse_scored_jobs_response",
    "score_jobs",
    "strip_job_for_ai",
    "strip_jobs_for_ai",
]
