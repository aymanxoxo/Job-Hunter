"""OpenRouter AI provider (SDD §7.3).

OpenRouter exposes an OpenAI-compatible chat-completions endpoint. This provider delegates prompt
orchestration, parsing, and scored-job construction to ``AIEngine`` (so it stays a thin HTTP
shell) and falls back to a secondary free model when the primary one errors (the free tier
rotates slugs and is rate-limited). The API key is read from an environment variable at call
time — never stored in config or logged (ADR-002 / SDD §8).
"""
from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx

from core.ai_engine import AIEngine, AIEngineError
from core.ai_providers._retry import http_call_with_retry
from core.ai_providers.base_provider import BaseAIProvider
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

DEFAULT_OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "qwen/qwen3-coder:free"
DEFAULT_OPENROUTER_FALLBACK_MODEL = "deepseek/deepseek-r1:free"
DEFAULT_OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
DEFAULT_OPENROUTER_TIMEOUT = 120.0

ClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]


class OpenRouterProviderError(RuntimeError):
    """Raised when OpenRouter returns an unusable response or no credential is available."""


class OpenRouterProvider(BaseAIProvider):
    """AI provider backed by OpenRouter's OpenAI-compatible chat-completions endpoint."""

    name = "openrouter"
    auth_methods = ("api_key",)
    supports_local = False

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_key_env: str = DEFAULT_OPENROUTER_API_KEY_ENV,
        model: str = DEFAULT_OPENROUTER_MODEL,
        fallback_model: str | None = DEFAULT_OPENROUTER_FALLBACK_MODEL,
        endpoint: str = DEFAULT_OPENROUTER_ENDPOINT,
        timeout: float = DEFAULT_OPENROUTER_TIMEOUT,
        batch_size: int = 15,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._api_key = api_key
        self.api_key_env = api_key_env
        self.model = model
        self.fallback_model = fallback_model
        self.endpoint = endpoint
        self.timeout = timeout
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self._client_factory = client_factory or self._default_client_factory

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        """Convert a plain-text profile into search criteria via OpenRouter."""
        try:
            return await self._engine().generate_criteria(profile)
        except AIEngineError as exc:
            raise OpenRouterProviderError(str(exc)) from exc

    async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
        """Score jobs via OpenRouter, returning new immutable Job copies."""
        try:
            return await self._engine().score_jobs(jobs, criteria)
        except AIEngineError as exc:
            raise OpenRouterProviderError(str(exc)) from exc

    async def _call(self, prompt: str) -> str:
        api_key = self._resolve_api_key()
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)
        last_error: OpenRouterProviderError | None = None
        async with self._client_factory() as client:
            for model in models:
                try:
                    return await self._call_model(client, model, prompt, api_key)
                except OpenRouterProviderError as exc:
                    last_error = exc
        raise last_error or OpenRouterProviderError("OpenRouter request failed.")

    async def _call_model(
        self, client: httpx.AsyncClient, model: str, prompt: str, api_key: str
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            response = await http_call_with_retry(
                lambda: client.post(
                    self.endpoint, json=payload, headers=headers, timeout=self.timeout
                ),
                max_attempts=self.max_attempts,
                base_delay=self.base_delay,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OpenRouterProviderError(
                f"OpenRouter request failed for model {model!r}."
            ) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise OpenRouterProviderError("OpenRouter response body was not valid JSON.") from exc
        return _extract_message_content(data)

    def _resolve_api_key(self) -> str:
        api_key = self._api_key if self._api_key is not None else os.environ.get(self.api_key_env)
        if not api_key:
            raise OpenRouterProviderError(
                f"OpenRouter API key not found; set the {self.api_key_env} environment variable."
            )
        return api_key

    def _engine(self) -> AIEngine:
        return AIEngine(self._call, batch_size=self.batch_size)

    def _default_client_factory(self) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        return httpx.AsyncClient()


def _extract_message_content(data: Any) -> str:
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        raise OpenRouterProviderError("OpenRouter response JSON must include non-empty 'choices'.")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise OpenRouterProviderError(
            "OpenRouter response choices must include string message content."
        )
    return content
