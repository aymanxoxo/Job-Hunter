"""C-030 - OpenRouter AI provider (SDD §7.3)."""
from __future__ import annotations

import json

import httpx
import pytest

from core.ai_providers import OpenRouterProvider as ExportedOpenRouterProvider
from core.ai_providers.openrouter_provider import (
    DEFAULT_OPENROUTER_API_KEY_ENV,
    DEFAULT_OPENROUTER_ENDPOINT,
    DEFAULT_OPENROUTER_FALLBACK_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    OpenRouterProvider,
    OpenRouterProviderError,
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


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _provider_for(handler, *, api_key: str | None = "test-key", **overrides) -> OpenRouterProvider:
    transport = httpx.MockTransport(handler)
    return OpenRouterProvider(
        api_key=api_key,
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        **overrides,
    )


async def test_openrouter_provider_metadata_matches_sdd():
    provider = OpenRouterProvider(api_key="test-key")

    assert provider.name == "openrouter"
    assert ExportedOpenRouterProvider is OpenRouterProvider
    assert provider.model == DEFAULT_OPENROUTER_MODEL == "qwen/qwen3-coder:free"
    assert provider.fallback_model == DEFAULT_OPENROUTER_FALLBACK_MODEL
    assert provider.fallback_model == "deepseek/deepseek-r1:free"
    assert provider.endpoint == DEFAULT_OPENROUTER_ENDPOINT
    assert provider.endpoint == "https://openrouter.ai/api/v1/chat/completions"
    assert provider.auth_methods == ("api_key",)
    assert provider.supports_local is False
    assert DEFAULT_OPENROUTER_API_KEY_ENV == "OPENROUTER_API_KEY"


async def test_generate_criteria_posts_openai_chat_with_bearer_auth():
    requests: list[dict] = []
    headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        headers.append(request.headers.get("authorization", ""))
        assert str(request.url) == DEFAULT_OPENROUTER_ENDPOINT
        return _chat_response(_CRITERIA_JSON)

    provider = _provider_for(handler, model="custom/model:free")

    criteria = await provider.generate_criteria("Senior Python developer")

    await assert_provider_generates_valid_criteria(provider, "Senior Python developer")
    assert criteria.titles == ("Python Developer",)
    assert criteria.keywords == ("python", "api")
    assert criteria.raw_profile == "Senior Python developer"
    assert requests[0]["model"] == "custom/model:free"
    assert requests[0]["messages"][0]["role"] == "user"
    assert requests[0]["messages"][0]["content"].endswith("USER: Senior Python developer")
    assert headers[0] == "Bearer test-key"


async def test_score_jobs_uses_engine_batching_and_stripped_payloads():
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        prompt = payload["messages"][0]["content"]
        prompts.append(prompt)
        jobs = json.loads(_extract_json_line(prompt, "      JOBS: "))
        scored = [
            {"id": job["id"], "score": 90, "match_reason": f"Matched {job['id']}", "red_flags": []}
            for job in jobs
        ]
        return _chat_response(json.dumps(scored))

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


async def test_falls_back_to_secondary_model_when_primary_errors():
    models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        models.append(model)
        if model == DEFAULT_OPENROUTER_MODEL:
            return httpx.Response(429, json={"error": {"message": "rate-limited"}})
        return _chat_response(_CRITERIA_JSON)

    provider = _provider_for(handler)

    criteria = await provider.generate_criteria("Senior Python developer")

    assert criteria.titles == ("Python Developer",)
    assert models == [DEFAULT_OPENROUTER_MODEL, DEFAULT_OPENROUTER_FALLBACK_MODEL]


async def test_raises_when_both_models_error():
    provider = _provider_for(lambda _r: httpx.Response(503, json={"error": "down"}))

    with pytest.raises(OpenRouterProviderError):
        await provider.generate_criteria("profile")


async def test_raises_for_missing_api_key(monkeypatch):
    monkeypatch.delenv(DEFAULT_OPENROUTER_API_KEY_ENV, raising=False)
    provider = OpenRouterProvider(api_key=None)

    with pytest.raises(OpenRouterProviderError, match="API key"):
        await provider.generate_criteria("profile")


async def test_reads_api_key_from_environment(monkeypatch):
    monkeypatch.setenv(DEFAULT_OPENROUTER_API_KEY_ENV, "env-key")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization", ""))
        return _chat_response(_CRITERIA_JSON)

    transport = httpx.MockTransport(handler)
    provider = OpenRouterProvider(
        api_key=None, client_factory=lambda: httpx.AsyncClient(transport=transport)
    )

    await provider.generate_criteria("profile")

    assert seen[0] == "Bearer env-key"


async def test_raises_for_response_without_choices():
    provider = _provider_for(lambda _r: httpx.Response(200, json={"choices": []}))

    with pytest.raises(OpenRouterProviderError, match="choices"):
        await provider.generate_criteria("profile")


async def test_raises_for_non_json_body():
    provider = _provider_for(lambda _r: httpx.Response(200, text="not json"))

    with pytest.raises(OpenRouterProviderError, match="JSON"):
        await provider.generate_criteria("profile")


def _extract_json_line(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing line starting with {prefix!r}")
