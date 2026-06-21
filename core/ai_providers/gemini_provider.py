"""Gemini AI provider (SDD §7.1).

Calls Google's Generative Language ``generateContent`` endpoint and delegates prompt orchestration,
parsing, and scored-job construction to ``AIEngine`` (thin HTTP shell, like the other providers).
Auth is resolved through the ordered ``auth_strategy`` (C-008): ``oauth`` is preferred when an OAuth
token provider is wired (lands with C-016), otherwise the ``api_key`` path reads ``GEMINI_API_KEY``.
Credentials are read at call time and never stored in config or logged (ADR-002 / SDD §8).
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx

from core.ai_engine import AIEngine, AIEngineError
from core.ai_providers._retry import http_call_with_retry
from core.ai_providers.base_provider import BaseAIProvider
from core.auth.auth_strategy import AuthProvider, AuthResult, resolve_auth
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

DEFAULT_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = "gemini-3-flash"
DEFAULT_GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_GEMINI_TIMEOUT = 120.0

ClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]


class GeminiProviderError(RuntimeError):
    """Raised when Gemini returns an unusable response or no credential is available."""


class GeminiProvider(BaseAIProvider):
    """AI provider backed by Google's Gemini ``generateContent`` endpoint."""

    name = "gemini"
    auth_methods = ("oauth", "api_key")
    supports_local = False

    def __init__(
        self,
        *,
        api_key_env: str = DEFAULT_GEMINI_API_KEY_ENV,
        model: str = DEFAULT_GEMINI_MODEL,
        endpoint: str = DEFAULT_GEMINI_ENDPOINT,
        timeout: float = DEFAULT_GEMINI_TIMEOUT,
        batch_size: int = 15,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        env: Mapping[str, str] | None = None,
        oauth_provider: AuthProvider | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.api_key_env = api_key_env
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self._env = env
        self._oauth_provider = oauth_provider
        self._client_factory = client_factory or self._default_client_factory

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        """Convert a plain-text profile into search criteria via Gemini."""
        try:
            return await self._engine().generate_criteria(profile)
        except AIEngineError as exc:
            raise GeminiProviderError(str(exc)) from exc

    async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
        """Score jobs via Gemini, returning new immutable Job copies."""
        try:
            return await self._engine().score_jobs(jobs, criteria)
        except AIEngineError as exc:
            raise GeminiProviderError(str(exc)) from exc

    async def _call(self, prompt: str) -> str:
        auth = self._resolve_auth()
        headers = self._auth_headers(auth)
        url = f"{self.endpoint}/{self.model}:generateContent"
        payload: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
        async with self._client_factory() as client:
            try:
                response = await http_call_with_retry(
                    lambda: client.post(url, json=payload, headers=headers, timeout=self.timeout),
                    max_attempts=self.max_attempts,
                    base_delay=self.base_delay,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise GeminiProviderError(f"Gemini request failed: {exc}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise GeminiProviderError("Gemini response body was not valid JSON.") from exc
        return _extract_text(data)

    def _resolve_auth(self) -> AuthResult:
        env = self._env if self._env is not None else os.environ
        result = resolve_auth(
            self.auth_methods,
            env=env,
            api_key_env_var=self.api_key_env,
            oauth_provider=self._oauth_provider,
            plugin_name=self.name,
        )
        if result is None:
            raise GeminiProviderError(
                f"No Gemini credential resolved; set {self.api_key_env} or configure OAuth."
            )
        return result

    def _auth_headers(self, auth: AuthResult) -> dict[str, str]:
        if auth.method == "oauth":
            return {"Authorization": f"Bearer {auth.credential}"}
        return {"x-goog-api-key": str(auth.credential)}

    def _engine(self) -> AIEngine:
        return AIEngine(self._call, batch_size=self.batch_size)

    def _default_client_factory(self) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        return httpx.AsyncClient()


def _extract_text(data: Any) -> str:
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not candidates:
        raise GeminiProviderError("Gemini response JSON must include non-empty 'candidates'.")
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    text = parts[0].get("text") if parts and isinstance(parts[0], dict) else None
    if not isinstance(text, str):
        raise GeminiProviderError("Gemini response candidates must include message text.")
    return text
