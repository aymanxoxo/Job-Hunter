"""C-054/C-064 — HTTP retry in all three providers (SDD §7)."""
from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from core.ai_providers.gemini_provider import GeminiProvider, GeminiProviderError
from core.ai_providers.ollama_provider import OllamaProvider, OllamaProviderError
from core.ai_providers.openrouter_provider import (
    OpenRouterProvider,
    OpenRouterProviderError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SequenceTransport(httpx.AsyncBaseTransport):
    """Returns responses from a pre-loaded list, one per request."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._iter: Iterator[httpx.Response] = iter(responses)
        self.call_count = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.call_count += 1
        return next(self._iter)


def _ollama_ok_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "response": json.dumps(
                {"titles": ["Dev"], "keywords": ["python"], "exclude_keywords": [],
                 "seniority_levels": [], "locations": []}
            ),
            "done": True,
        },
    )


def _gemini_ok_response() -> httpx.Response:
    payload = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(
                {"titles": ["Dev"], "keywords": ["python"], "exclude_keywords": [],
                 "seniority_levels": [], "locations": []}
            )}]}}
        ]
    }
    return httpx.Response(200, json=payload)


def _openrouter_ok_response() -> httpx.Response:
    payload = {
        "choices": [
            {"message": {"content": json.dumps(
                {"titles": ["Dev"], "keywords": ["python"], "exclude_keywords": [],
                 "seniority_levels": [], "locations": []}
            )}}
        ]
    }
    return httpx.Response(200, json=payload)


def _err(status: int) -> httpx.Response:
    return httpx.Response(status, json={"error": "transient"})


def _err_with_headers(status: int, headers: dict[str, str]) -> httpx.Response:
    return httpx.Response(status, json={"error": "transient"}, headers=headers)


def _make_ollama(transport: _SequenceTransport, **kw) -> OllamaProvider:
    return OllamaProvider(
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        **kw,
    )


def _make_gemini(transport: _SequenceTransport, **kw) -> GeminiProvider:
    return GeminiProvider(
        env={"GEMINI_API_KEY": "test-key"},
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        **kw,
    )


def _make_openrouter(transport: _SequenceTransport, **kw) -> OpenRouterProvider:
    return OpenRouterProvider(
        env={"OPENROUTER_API_KEY": "test-key"},
        fallback_model=None,
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        **kw,
    )


# ---------------------------------------------------------------------------
# Ollama retry tests
# ---------------------------------------------------------------------------


async def test_ollama_retry_succeeds_after_transient_503():
    t = _SequenceTransport([_err(503), _err(503), _ollama_ok_response()])
    provider = _make_ollama(t, max_attempts=3, base_delay=0.0)
    criteria = await provider.generate_criteria("python dev")
    assert criteria.keywords == ("python",)
    assert t.call_count == 3


async def test_ollama_retry_gives_up_after_max_attempts():
    t = _SequenceTransport([_err(503), _err(503), _err(503)])
    provider = _make_ollama(t, max_attempts=3, base_delay=0.0)
    with pytest.raises(OllamaProviderError):
        await provider.generate_criteria("python dev")
    assert t.call_count == 3


async def test_ollama_no_retry_on_401():
    t = _SequenceTransport([_err(401)])
    provider = _make_ollama(t, max_attempts=3, base_delay=0.0)
    with pytest.raises(OllamaProviderError):
        await provider.generate_criteria("python dev")
    assert t.call_count == 1


async def test_ollama_retry_on_429():
    t = _SequenceTransport([_err(429), _ollama_ok_response()])
    provider = _make_ollama(t, max_attempts=3, base_delay=0.0)
    criteria = await provider.generate_criteria("python dev")
    assert criteria is not None
    assert t.call_count == 2


async def test_ollama_retry_honors_retry_after_header(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("core.ai_providers._retry.asyncio.sleep", fake_sleep)
    t = _SequenceTransport([_err_with_headers(429, {"Retry-After": "2"}), _ollama_ok_response()])
    provider = _make_ollama(t, max_attempts=3, base_delay=0.0)

    criteria = await provider.generate_criteria("python dev")

    assert criteria is not None
    assert sleeps == [2.0]
    assert t.call_count == 2


async def test_ollama_retry_on_network_error():
    call_count = 0

    class _NetworkErrTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.NetworkError("connection refused")
            return _ollama_ok_response()

    provider = OllamaProvider(
        client_factory=lambda: httpx.AsyncClient(transport=_NetworkErrTransport()),
        max_attempts=3,
        base_delay=0.0,
    )
    criteria = await provider.generate_criteria("python dev")
    assert criteria is not None
    assert call_count == 2


async def test_retry_rejects_non_positive_max_attempts():
    t = _SequenceTransport([_ollama_ok_response()])
    provider = _make_ollama(t, max_attempts=0, base_delay=0.0)

    with pytest.raises(ValueError, match="max_attempts"):
        await provider.generate_criteria("python dev")

    assert t.call_count == 0


async def test_retry_after_header_is_capped_at_max(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("core.ai_providers._retry.asyncio.sleep", fake_sleep)
    t = _SequenceTransport([_err_with_headers(429, {"Retry-After": "3600"}), _ollama_ok_response()])
    provider = _make_ollama(t, max_attempts=3, base_delay=0.0)

    criteria = await provider.generate_criteria("python dev")

    assert criteria is not None
    assert sleeps == [60.0]
    assert t.call_count == 2


# ---------------------------------------------------------------------------
# Gemini retry tests
# ---------------------------------------------------------------------------


async def test_gemini_retry_succeeds_after_transient_503():
    t = _SequenceTransport([_err(503), _err(503), _gemini_ok_response()])
    provider = _make_gemini(t, max_attempts=3, base_delay=0.0)
    criteria = await provider.generate_criteria("python dev")
    assert criteria is not None
    assert t.call_count == 3


async def test_gemini_no_retry_on_401():
    t = _SequenceTransport([_err(401)])
    provider = _make_gemini(t, max_attempts=3, base_delay=0.0)
    with pytest.raises(GeminiProviderError):
        await provider.generate_criteria("python dev")
    assert t.call_count == 1


async def test_gemini_retry_on_429():
    t = _SequenceTransport([_err(429), _gemini_ok_response()])
    provider = _make_gemini(t, max_attempts=3, base_delay=0.0)
    criteria = await provider.generate_criteria("python dev")
    assert criteria is not None
    assert t.call_count == 2


# ---------------------------------------------------------------------------
# OpenRouter retry tests (within a single model attempt)
# ---------------------------------------------------------------------------


async def test_openrouter_retry_succeeds_after_transient_503():
    t = _SequenceTransport([_err(503), _err(503), _openrouter_ok_response()])
    provider = _make_openrouter(t, max_attempts=3, base_delay=0.0)
    criteria = await provider.generate_criteria("python dev")
    assert criteria is not None
    assert t.call_count == 3


async def test_openrouter_no_retry_on_401():
    t = _SequenceTransport([_err(401)])
    provider = _make_openrouter(t, max_attempts=3, base_delay=0.0)
    with pytest.raises(OpenRouterProviderError):
        await provider.generate_criteria("python dev")
    assert t.call_count == 1
