"""Offline fixture-backed connector for development and tests (SDD section 6.3)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from core.connectors.base_connector import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

DEFAULT_FIXTURE_PATH = Path("fixtures/jobs.json")


class MockConnector(BaseConnector):
    """Load deterministic jobs from a JSON fixture and filter them by keyword."""

    name = "mock"
    auth_methods = ("none",)

    def __init__(self, fixture_path: str | Path = DEFAULT_FIXTURE_PATH) -> None:
        self.fixture_path = Path(fixture_path)

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        """Return fixture jobs matching any criteria keyword in title or description."""
        jobs = self._load_jobs()
        if not criteria.keywords:
            return jobs
        return [job for job in jobs if _matches_keywords(job, criteria.keywords)]

    def _load_jobs(self) -> list[Job]:
        try:
            payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Mock fixture is not valid JSON: {self.fixture_path}") from exc
        if not isinstance(payload, list):
            raise ValueError("Mock fixture must contain a JSON array of jobs.")
        return [_job_from_fixture(item) for item in payload]


def _job_from_fixture(item: Any) -> Job:
    if not isinstance(item, dict):
        raise ValueError("Mock fixture jobs must be JSON objects.")
    data = {**item, "source": MockConnector.name}
    try:
        return Job(**data)
    except ValidationError as exc:
        raise ValueError("Mock fixture contains an invalid job record.") from exc


def _matches_keywords(job: Job, keywords: tuple[str, ...]) -> bool:
    haystack = " ".join(value.lower() for value in (job.title, job.description or ""))
    return any(keyword.lower() in haystack for keyword in keywords)
