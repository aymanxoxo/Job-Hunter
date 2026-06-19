"""AI engine facade and pure helper exports."""
from __future__ import annotations

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


@dataclass(frozen=True)
class AIEngine:
    """Async facade that turns provider text responses into JobHunter models."""

    call_provider: ProviderCall
    batch_size: int = 15

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        """Generate structured search criteria from a plain-text profile."""
        prompt = build_generate_criteria_prompt(profile)
        response = await self.call_provider(prompt)
        criteria = parse_criteria_response(response, raw_profile=profile)
        if criteria is None:
            raise AIEngineError("Provider returned invalid criteria JSON.")
        return criteria

    async def score_jobs(self, jobs: Sequence[Job], criteria: SearchCriteria) -> list[Job]:
        """Score jobs in batches without mutating the input jobs."""
        scored_jobs: list[Job] = []
        for batch in batch_items(jobs, batch_size=self.batch_size):
            prompt = build_score_jobs_prompt(criteria, batch)
            response = await self.call_provider(prompt)
            scored_batch = parse_scored_jobs_response(response, batch)
            if scored_batch is None:
                raise AIEngineError("Provider returned invalid score JSON.")
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
) -> list[Job]:
    """Score jobs with a one-off engine facade."""
    return await AIEngine(call_provider, batch_size=batch_size).score_jobs(jobs, criteria)

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
