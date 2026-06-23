"""BaseAIProvider — the plugin contract every AI provider implements (SDD §4.2).

An AI provider converts profile text into search criteria and scores raw jobs. Auth is declared as
an ordered ``auth_methods`` tuple resolved by the runner (ADR-002); providers may also mark
themselves as local-only with ``supports_local``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.models.job import Job
from core.models.search_criteria import SearchCriteria


class BaseAIProvider(ABC):
    """Contract for an AI backend. Subclasses must implement criteria generation and scoring."""

    name: str = "unnamed"
    auth_methods: tuple[str, ...] = ("api_key",)
    supports_local: bool = False

    @abstractmethod
    async def generate_criteria(self, profile: str) -> SearchCriteria:
        """Convert a plain-text profile/CV into a SearchCriteria object."""
        raise NotImplementedError

    @abstractmethod
    async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
        """Score jobs and return new Job objects with score details populated."""
        raise NotImplementedError

    async def initialize(self) -> None:
        """Optional startup hook for auth token refresh, health checks, or readiness checks."""
        return None

    async def complete(self, prompt: str) -> str:
        """Raw text completion — used by connectors that need AI internally (e.g. DDGConnector).
        Not abstract; providers that don't expose this raise NotImplementedError."""
        raise NotImplementedError(f"{type(self).__name__} does not implement complete()")
