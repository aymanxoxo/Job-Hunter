"""C-015 - Ollama AI provider."""
from __future__ import annotations

import json

import httpx
import pytest

from core.ai_providers import OllamaProvider as ExportedOllamaProvider
from core.ai_providers.ollama_provider import (
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
    OllamaProvider,
    OllamaProviderError,
)
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from tests.contracts.provider_contract import (
    assert_provider_generates_valid_criteria,
    assert_provider_scores_valid_jobs,
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


def _provider_for(handler, **overrides) -> OllamaProvider:
    transport = httpx.MockTransport(handler)
    return OllamaProvider(
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        **overrides,
    )


async def test_ollama_provider_metadata_matches_sdd():
    provider = OllamaProvider()

    assert provider.name == "ollama"
    assert ExportedOllamaProvider is OllamaProvider
    assert provider.model == DEFAULT_OLLAMA_MODEL == "llama3"
    assert provider.endpoint == DEFAULT_OLLAMA_ENDPOINT == "http://localhost:11434/api/generate"
    assert provider.auth_methods == ("none",)
    assert provider.supports_local is True


async def test_generate_criteria_posts_to_ollama_and_parses_response():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        assert str(request.url) == DEFAULT_OLLAMA_ENDPOINT
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    {
                        "titles": ["Python Developer"],
                        "keywords": ["python", "api"],
                        "exclude_keywords": ["manager"],
                        "seniority_levels": ["senior"],
                        "locations": ["remote"],
                    }
                ),
                "done": True,
            },
        )

    provider = _provider_for(handler, model="custom-model")

    criteria = await provider.generate_criteria("Senior Python developer")

    await assert_provider_generates_valid_criteria(provider, "Senior Python developer")
    assert criteria.titles == ("Python Developer",)
    assert criteria.keywords == ("python", "api")
    assert criteria.raw_profile == "Senior Python developer"
    assert requests[0]["model"] == "custom-model"
    assert requests[0]["stream"] is False
    assert requests[0]["prompt"].startswith("SYSTEM: You are a career advisor.")
    assert requests[0]["prompt"].endswith("USER: Senior Python developer")


async def test_score_jobs_uses_engine_batching_and_stripped_payloads():
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        prompts.append(payload["prompt"])
        jobs = json.loads(_extract_json_line(payload["prompt"], "      JOBS: "))
        return httpx.Response(
            200,
            json={
                "response": json.dumps(
                    [
                        {
                            "id": job["id"],
                            "score": 90,
                            "match_reason": f"Matched {job['id']}",
                            "red_flags": [],
                        }
                        for job in jobs
                    ]
                ),
                "done": True,
            },
        )

    provider = _provider_for(handler, batch_size=1)
    first = _job(id="job-1")
    second = _job(id="job-2", url="https://example.invalid/job-2")

    scored = await provider.score_jobs([first, second], SearchCriteria(keywords=("python",)))

    await assert_provider_scores_valid_jobs(provider, [first], SearchCriteria())
    assert [job.id for job in scored] == ["job-1", "job-2"]
    assert [job.score for job in scored] == [90, 90]
    assert [job.match_reason for job in scored] == ["Matched job-1", "Matched job-2"]
    assert [job.score for job in [first, second]] == [None, None]
    assert len(prompts) == 3
    assert all("https://example.invalid" not in prompt for prompt in prompts)
    assert all("<secret>" not in prompt for prompt in prompts)
    assert all('"source"' not in prompt for prompt in prompts)


async def test_ollama_provider_raises_for_missing_response_field():
    provider = _provider_for(lambda _request: httpx.Response(200, json={"done": True}))

    with pytest.raises(OllamaProviderError, match="response"):
        await provider.generate_criteria("profile")


async def test_ollama_provider_raises_for_non_json_body():
    provider = _provider_for(lambda _request: httpx.Response(200, text="not json"))

    with pytest.raises(OllamaProviderError, match="JSON"):
        await provider.generate_criteria("profile")


async def test_ollama_provider_raises_for_invalid_engine_json():
    provider = _provider_for(
        lambda _request: httpx.Response(200, json={"response": "not criteria json"})
    )

    with pytest.raises(OllamaProviderError, match="criteria"):
        await provider.generate_criteria("profile")


def _extract_json_line(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing line starting with {prefix!r}")
