"""BaseConnector — the plugin contract every job connector implements (SDD §4.1).

A connector fetches raw (unscored) jobs from one source. Auth is declared as an ordered
``auth_methods`` tuple resolved by the runner (ADR-002); ``("none",)`` means no auth. Connectors are
independent — they never import one another (ADR-001).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.models.job import Job
from core.models.search_criteria import SearchCriteria


class BaseConnector(ABC):
    """Contract for a job-board connector. Subclasses must implement :meth:`search`."""

    name: str = "unnamed"
    auth_methods: tuple[str, ...] = ("none",)
    enabled: bool = True

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> list[Job]:
        """Execute the search and return a raw (unscored) list of jobs."""
        raise NotImplementedError

    async def authenticate(self) -> bool:
        """Called by the runner before :meth:`search` when auth is required.

        Return True if authentication succeeded, False to skip this connector (fail-graceful). The
        default is a no-op suitable for ``auth_methods == ("none",)``.
        """
        return True
