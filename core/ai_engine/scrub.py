"""Pure job payload scrubbing before AI provider calls (SDD §5.2 IMPORTANT)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.models.job import Job


def strip_job_for_ai(job: Job) -> dict[str, Any]:
    """Return only the fields allowed in SCORE_JOBS provider payloads."""
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "description": job.description,
    }


def strip_jobs_for_ai(jobs: Sequence[Job]) -> list[dict[str, Any]]:
    """Strip a sequence of jobs while preserving order."""
    return [strip_job_for_ai(job) for job in jobs]
