"""Reusable connector contract check (SDD §12.2).

Every connector — built-in or user drop-in — must return a ``list[Job]``. This helper is applied by
per-connector tests and, once plugin discovery (C-009) exists, parametrised over all discovered
connectors.
"""
from __future__ import annotations

from core.connectors.base_connector import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria


async def assert_connector_returns_valid_jobs(
    connector: BaseConnector, criteria: SearchCriteria
) -> None:
    """Run ``connector.search`` and assert every result is a valid ``Job``.

    The contract is ``search(criteria) -> list[Job]``: each item must be a ``Job`` instance (not a
    duck-typed look-alike) and must carry the connector's ``name`` as its source.
    """
    jobs = await connector.search(criteria)
    assert isinstance(jobs, list)
    for job in jobs:
        assert isinstance(job, Job), f"{connector.name} returned a non-Job: {type(job).__name__}"
        assert job.id and job.title and job.company and job.url
        assert job.source == connector.name
