"""Local Ollama AI provider (SDD section 7.2)."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx

from core.ai_engine import AIEngine, AIEngineError
from core.ai_providers._retry import http_call_with_retry
from core.ai_providers.base_provider import BaseAIProvider
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "llama3"
DEFAULT_OLLAMA_TIMEOUT = 120.0

ClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]


class OllamaProviderError(RuntimeError):
    """Raised when Ollama returns an unusable response."""


class OllamaProvider(BaseAIProvider):
    """AI provider backed by a local Ollama `/api/generate` endpoint."""

    name = "ollama"
    auth_methods = ("none",)
    supports_local = True

    def __init__(
        self,
        *,
        model: str = DEFAULT_OLLAMA_MODEL,
        endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
        timeout: float = DEFAULT_OLLAMA_TIMEOUT,
        batch_size: int = 15,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self._client_factory = client_factory or self._default_client_factory

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        """Convert a plain-text profile into search criteria via Ollama."""
        try:
            return await self._engine().generate_criteria(profile)
        except AIEngineError as exc:
            raise OllamaProviderError(str(exc)) from exc

    async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
        """Score jobs via Ollama, returning new immutable Job copies."""
        try:
            return await self._engine().score_jobs(jobs, criteria)
        except AIEngineError as exc:
            raise OllamaProviderError(str(exc)) from exc

    async def complete(self, prompt: str) -> str:
        """Raw text completion for connectors that need AI internally."""
        return await self._call(prompt)

    async def _call(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        async with self._client_factory() as client:
            try:
                response = await http_call_with_retry(
                    lambda: client.post(self.endpoint, json=payload, timeout=self.timeout),
                    max_attempts=self.max_attempts,
                    base_delay=self.base_delay,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise OllamaProviderError(f"Ollama request failed: {exc}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaProviderError("Ollama response body was not valid JSON.") from exc
        provider_text = data.get("response") if isinstance(data, dict) else None
        if not isinstance(provider_text, str):
            raise OllamaProviderError("Ollama response JSON must include a string response field.")
        return provider_text

    def _engine(self) -> AIEngine:
        return AIEngine(self._call, batch_size=self.batch_size)

    def _default_client_factory(self) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        return httpx.AsyncClient()
