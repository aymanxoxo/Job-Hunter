"""C-051 - Adzuna connector."""
from __future__ import annotations

import httpx
import pytest

from core.connectors import AdzunaConnector as ExportedAdzunaConnector
from core.connectors.adzuna_connector import (
    ADZUNA_ENDPOINT_TEMPLATE,
    DEFAULT_ADZUNA_COUNTRY,
    AdzunaConnector,
    AdzunaConnectorError,
)
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from tests.contracts.connector_contract import assert_connector_returns_valid_jobs


def _connector_for(handler, **overrides) -> AdzunaConnector:
    transport = httpx.MockTransport(handler)
    kwargs = {"app_id": "app-id", "app_key": "app-key"}
    kwargs.update(overrides)
    return AdzunaConnector(
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        **kwargs,
    )


def _response(job_overrides: dict | None = None) -> dict:
    job = {
        "id": "123",
        "title": "Senior Python Developer",
        "company": {"display_name": "Acme"},
        "redirect_url": "https://www.adzuna.com/jobs/details/123",
        "location": {"display_name": "Remote, United States"},
        "description": "Build async Python APIs.",
        "salary_min": 120000,
        "salary_max": 150000,
        "created": "2026-06-19T12:34:56Z",
    }
    job.update(job_overrides or {})
    return {"results": [job]}


async def test_adzuna_connector_metadata_matches_backlog():
    connector = AdzunaConnector(app_id="id", app_key="key")

    assert connector.name == "adzuna"
    assert ExportedAdzunaConnector is AdzunaConnector
    assert connector.auth_methods == ("api_key",)
    assert connector.country == DEFAULT_ADZUNA_COUNTRY == "us"
    assert connector.endpoint_template == ADZUNA_ENDPOINT_TEMPLATE


async def test_search_builds_adzuna_request_from_criteria_and_maps_jobs():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/v1/api/jobs/us/search/1"
        params = dict(request.url.params)
        assert params["app_id"] == "app-id"
        assert params["app_key"] == "app-key"
        assert params["results_per_page"] == "1"
        assert params["what"] == "Senior Python Developer python async"
        assert params["what_exclude"] == "contract"
        assert params["where"] == "Remote"
        assert params["content-type"] == "application/json"
        return httpx.Response(200, json=_response())

    # max_results=1: one result fills the limit so the loop exits after a single page
    connector = _connector_for(handler, max_results=1)

    jobs = await connector.search(
        SearchCriteria(
            titles=("Senior Python Developer",),
            keywords=("python", "async"),
            exclude_keywords=("contract",),
            locations=("Remote",),
        )
    )

    contract_connector = _connector_for(
        lambda _request: httpx.Response(200, json=_response()), max_results=1
    )
    await assert_connector_returns_valid_jobs(
        contract_connector, SearchCriteria(keywords=("python",))
    )
    assert len(requests) == 1
    assert jobs == [
        Job(
            id="adzuna-123",
            title="Senior Python Developer",
            company="Acme",
            url="https://www.adzuna.com/jobs/details/123",
            source="adzuna",
            location="Remote, United States",
            description="Build async Python APIs.",
            salary_range="$120,000 - $150,000",
            posted_date="2026-06-19T12:34:56Z",
            raw=_response()["results"][0],
        )
    ]


async def test_search_reads_credentials_from_named_environment(monkeypatch):
    monkeypatch.setenv("ADZUNA_TEST_ID", "env-id")
    monkeypatch.setenv("ADZUNA_TEST_KEY", "env-key")
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={"results": []})

    connector = _connector_for(
        handler,
        app_id=None,
        app_key=None,
        app_id_env="ADZUNA_TEST_ID",
        app_key_env="ADZUNA_TEST_KEY",
    )

    assert await connector.search(SearchCriteria()) == []
    assert seen[0]["app_id"] == "env-id"
    assert seen[0]["app_key"] == "env-key"


async def test_search_missing_credentials_raises_clear_error(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    connector = AdzunaConnector()

    with pytest.raises(AdzunaConnectorError, match="ADZUNA_APP_ID"):
        await connector.search(SearchCriteria())


async def test_search_raises_for_http_error():
    connector = _connector_for(lambda _request: httpx.Response(401, json={"error": "bad key"}))

    with pytest.raises(AdzunaConnectorError, match="401"):
        await connector.search(SearchCriteria())


async def test_search_raises_for_invalid_json_body():
    connector = _connector_for(lambda _request: httpx.Response(200, text="not json"))

    with pytest.raises(AdzunaConnectorError, match="JSON"):
        await connector.search(SearchCriteria())


async def test_search_skips_incomplete_result_records():
    connector = _connector_for(
        lambda _request: httpx.Response(
            200,
            json={
                "results": [
                    {"id": "missing-title", "company": {"display_name": "Acme"}},
                    _response({"id": "ok"})["results"][0],
                ]
            },
        ),
        max_results=1,  # one valid job satisfies the limit; loop exits after page 1
    )

    jobs = await connector.search(SearchCriteria())

    assert [job.id for job in jobs] == ["adzuna-ok"]


def test_config_defaults_include_adzuna_env_var_names():
    from core.config import Config

    config = Config()

    assert config.auth.adzuna_app_id_env == "ADZUNA_APP_ID"
    assert config.auth.adzuna_app_key_env == "ADZUNA_APP_KEY"
