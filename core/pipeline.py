"""Pure pipeline transforms for merging, deduping, sorting, and filtering jobs."""
from __future__ import annotations

from collections.abc import Iterable

from core.models.job import Job


def merge_results(connector_results: Iterable[Iterable[Job]]) -> list[Job]:
    """Flatten connector result groups while preserving connector and job order."""
    return [job for jobs in connector_results for job in jobs]


def dedup_by_url(jobs: Iterable[Job]) -> list[Job]:
    """Return the first job for each URL, preserving first-seen order."""
    seen: set[str] = set()
    deduped: list[Job] = []
    for job in jobs:
        if job.url in seen:
            continue
        seen.add(job.url)
        deduped.append(job)
    return deduped


def sort_by_score(jobs: Iterable[Job]) -> list[Job]:
    """Sort jobs by score descending, treating unscored jobs as zero."""
    return sorted(jobs, key=lambda job: job.score or 0, reverse=True)


def filter_below_threshold(jobs: Iterable[Job], *, min_score_threshold: int) -> list[Job]:
    """Keep scored jobs whose score is at or above the effective threshold."""
    return [
        job
        for job in jobs
        if job.score is not None and job.score >= min_score_threshold
    ]
