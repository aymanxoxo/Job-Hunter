"""C-017 - Gemini AI provider (SDD §7.1)."""
from __future__ import annotations

import json

import httpx
import pytest

from core.ai_providers import GeminiProvider as ExportedGeminiProvider
from core.ai_providers.gemini_provider import (
    DEFAULT_GEMINI_API_KEY_ENV,
    DEFAULT_GEMINI_ENDPOINT,
    DEFAULT_GEMINI_MODEL,
    GeminiProvider,
    GeminiProviderError,
)
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from tests.contracts.provider_contract import (
    assert_provider_generates_valid_criteria,
    assert_provider_scores_valid_jobs,
)

_CRITERIA_JSON = json.dumps(
    {
        "titles": ["Python Developer"],
        "keywords": ["python", "api"],
        "exclude_keywords": ["manager"],
        "seniority_levels": ["senior"],
        "locations": ["remote"],
    }
)


def _job(**overrides) -> Job:
    data = {
        "id": "job-1",
        "title": "Python Developer",
        "company": "Acme",
        "url": "https://example.invalid/job-1",
        "source": "mock",
        "description": "Build APIs.",
        "raw": {"html": "<secret>"},
    }
    data.update(overrides)
    return Job(**data)


def _gemini_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def _provider_for(handler, *, env=None, **overrides) -> GeminiProvider:
    transport = httpx.MockTransport(handler)
    return GeminiProvider(
        env={"GEMINI_API_KEY": "test-key"} if env is None else env,
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        **overrides,
    )


async def test_gemini_provider_metadata_matches_sdd():
    provider = GeminiProvider(env={"GEMINI_API_KEY": "test-key"})

    assert provider.name == "gemini"
    assert ExportedGeminiProvider is GeminiProvider
    assert provider.model == DEFAULT_GEMINI_MODEL == "gemini-3.5-flash"
    assert provider.endpoint == DEFAULT_GEMINI_ENDPOINT
    assert provider.endpoint == "https://generativelanguage.googleapis.com/v1beta/models"
    assert provider.auth_methods == ("oauth", "api_key")
    assert provider.supports_local is False
    assert DEFAULT_GEMINI_API_KEY_ENV == "GEMINI_API_KEY"


async def test_generate_criteria_posts_generatecontent_with_api_key_header():
    requests: list[dict] = []
    urls: list[str] = []
    headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        urls.append(str(request.url))
        headers.append(request.headers.get("x-goog-api-key", ""))
        return _gemini_response(_CRITERIA_JSON)

    provider = _provider_for(handler, model="gemini-custom")

    criteria = await provider.generate_criteria("Senior Python developer")

    await assert_provider_generates_valid_criteria(provider, "Senior Python developer")
    assert criteria.titles == ("Python Developer",)
    assert criteria.keywords == ("python", "api")
    assert criteria.raw_profile == "Senior Python developer"
    assert urls[0].endswith("/models/gemini-custom:generateContent")
    assert headers[0] == "test-key"
    assert requests[0]["contents"][0]["parts"][0]["text"].endswith("USER: Senior Python developer")


async def test_score_jobs_uses_engine_batching_and_stripped_payloads():
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        prompt = payload["contents"][0]["parts"][0]["text"]
        prompts.append(prompt)
        jobs = json.loads(_extract_json_line(prompt, "      JOBS: "))
        scored = [
            {"id": job["id"], "score": 90, "match_reason": f"Matched {job['id']}", "red_flags": []}
            for job in jobs
        ]
        return _gemini_response(json.dumps(scored))

    provider = _provider_for(handler, batch_size=1)
    first = _job(id="job-1")
    second = _job(id="job-2", url="https://example.invalid/job-2")

    scored = await provider.score_jobs([first, second], SearchCriteria(keywords=("python",)))

    await assert_provider_scores_valid_jobs(provider, [first], SearchCriteria())
    assert [job.id for job in scored] == ["job-1", "job-2"]
    assert [job.score for job in scored] == [90, 90]
    assert [job.score for job in [first, second]] == [None, None]
    assert all("https://example.invalid" not in prompt for prompt in prompts)
    assert all("<secret>" not in prompt for prompt in prompts)
    assert all('"source"' not in prompt for prompt in prompts)


async def test_prefers_oauth_when_an_oauth_token_is_available():
    seen_auth: list[str] = []
    seen_key: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("authorization", ""))
        seen_key.append(request.headers.get("x-goog-api-key", ""))
        return _gemini_response(_CRITERIA_JSON)

    transport = httpx.MockTransport(handler)
    provider = GeminiProvider(
        env={"GEMINI_API_KEY": "test-key"},
        oauth_provider=lambda: "oauth-token",
        client_factory=lambda: httpx.AsyncClient(transport=transport),
    )

    await provider.generate_criteria("profile")

    assert seen_auth[0] == "Bearer oauth-token"
    assert seen_key[0] == ""


async def test_raises_when_no_credential_available():
    provider = GeminiProvider(env={})

    with pytest.raises(GeminiProviderError, match="credential"):
        await provider.generate_criteria("profile")


async def test_reads_api_key_from_os_environ(monkeypatch):
    monkeypatch.setenv(DEFAULT_GEMINI_API_KEY_ENV, "env-key")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("x-goog-api-key", ""))
        return _gemini_response(_CRITERIA_JSON)

    transport = httpx.MockTransport(handler)
    provider = GeminiProvider(client_factory=lambda: httpx.AsyncClient(transport=transport))

    await provider.generate_criteria("profile")

    assert seen[0] == "env-key"


async def test_raises_for_response_without_candidates():
    provider = _provider_for(lambda _r: httpx.Response(200, json={"candidates": []}))

    with pytest.raises(GeminiProviderError, match="candidates"):
        await provider.generate_criteria("profile")


async def test_raises_for_non_json_body():
    provider = _provider_for(lambda _r: httpx.Response(200, text="not json"))

    with pytest.raises(GeminiProviderError, match="JSON"):
        await provider.generate_criteria("profile")


async def test_raises_for_http_error_status():
    provider = _provider_for(lambda _r: httpx.Response(429, json={"error": "rate"}))

    with pytest.raises(GeminiProviderError):
        await provider.generate_criteria("profile")


def _extract_json_line(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing line starting with {prefix!r}")
