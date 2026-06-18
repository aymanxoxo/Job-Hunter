"""C-039 walking skeleton: a thin profile -> scored jobs pipeline.

These stubs prove integration wiring before the real runner, output module, mock connector, and CLI
chunks land. Keep behavior deliberately small and deterministic so later chunks can replace it
cleanly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.ai_providers import BaseAIProvider
from core.connectors import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

DEFAULT_FIXTURE_PATH = Path("fixtures/jobs.json")
DEFAULT_OUTPUT_PATH = Path("output/walking_skeleton_results.json")
_GENERIC_REASON_TERMS = {"developer", "engineer", "senior"}
_KNOWN_KEYWORDS = (
    "python",
    "developer",
    "engineer",
    "remote",
    "async",
    "api",
    "data",
)


@dataclass(frozen=True)
class WalkingSkeletonResult:
    """End-to-end skeleton output returned to the CLI and tests."""

    criteria: SearchCriteria
    jobs: tuple[Job, ...]
    output_path: Path


class StubAIProvider(BaseAIProvider):
    """Deterministic AI-provider stub for the walking skeleton."""

    name = "walking-skeleton-ai"
    auth_methods = ("none",)
    supports_local = True

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        normalized = profile.lower()
        keywords = tuple(keyword for keyword in _KNOWN_KEYWORDS if keyword in normalized)
        locations = ("remote",) if "remote" in keywords else ()
        titles = _titles_from_profile(normalized)
        return SearchCriteria(
            titles=titles,
            keywords=keywords,
            locations=locations,
            raw_profile=profile,
        )

    async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
        scored: list[Job] = []
        for job in jobs:
            matched = _matched_keywords(job, criteria)
            reason_terms = tuple(term for term in matched if term not in _GENERIC_REASON_TERMS)
            score = min(100, 50 + (20 * len(reason_terms)))
            scored.append(
                job.model_copy(
                    update={
                        "score": score,
                        "match_reason": _match_reason(reason_terms),
                        "red_flags": (),
                    }
                )
            )
        return scored


class FixtureConnector(BaseConnector):
    """Loads raw jobs from a JSON fixture file."""

    name = "walking-skeleton-fixture"
    auth_methods = ("none",)

    def __init__(self, fixture_path: str | Path = DEFAULT_FIXTURE_PATH) -> None:
        self.fixture_path = Path(fixture_path)

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        jobs = load_fixture_jobs(self.fixture_path)
        if not criteria.keywords:
            return jobs
        return [job for job in jobs if _matched_keywords(job, criteria)]


async def run_walking_skeleton(
    profile: str,
    *,
    fixture_path: str | Path = DEFAULT_FIXTURE_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    provider: BaseAIProvider | None = None,
    connector: BaseConnector | None = None,
) -> WalkingSkeletonResult:
    """Run the C-039 profile -> criteria -> search -> score -> export slice."""

    selected_provider = provider or StubAIProvider()
    selected_connector = connector or FixtureConnector(fixture_path)
    criteria = await selected_provider.generate_criteria(profile)
    raw_jobs = await selected_connector.search(criteria)
    scored_jobs = await selected_provider.score_jobs(raw_jobs, criteria)
    ordered_jobs = tuple(sorted(scored_jobs, key=lambda job: job.score or 0, reverse=True))
    destination = Path(output_path)
    write_results(destination, criteria, ordered_jobs)
    return WalkingSkeletonResult(criteria=criteria, jobs=ordered_jobs, output_path=destination)


def load_fixture_jobs(path: str | Path) -> list[Job]:
    """Load Job objects from a fixture JSON array."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Job fixture must contain a JSON array")
    return [Job(**item) for item in payload]


def write_results(path: str | Path, criteria: SearchCriteria, jobs: tuple[Job, ...]) -> None:
    """Write skeleton results to JSON."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "criteria": criteria.model_dump(mode="json"),
        "jobs": [job.model_dump(mode="json") for job in jobs],
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _titles_from_profile(normalized_profile: str) -> tuple[str, ...]:
    if "python" not in normalized_profile:
        return ()
    prefix = "Senior " if "senior" in normalized_profile else ""
    role = "Developer" if "developer" in normalized_profile else "Engineer"
    return (f"{prefix}Python {role}",)


def _matched_keywords(job: Job, criteria: SearchCriteria) -> tuple[str, ...]:
    haystack = _job_haystack(job)
    return tuple(keyword for keyword in criteria.keywords if keyword.lower() in haystack)


def _job_haystack(job: Job) -> str:
    values: tuple[Any, ...] = (
        job.title,
        job.company,
        job.location,
        job.description,
        job.salary_range,
        job.source,
    )
    return " ".join(str(value).lower() for value in values if value)


def _match_reason(matched: tuple[str, ...]) -> str:
    if not matched:
        return "No keyword match"
    return "Matched: " + ", ".join(matched)
