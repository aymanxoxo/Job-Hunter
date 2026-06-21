"""C-055 — Adzuna pagination (SDD §6.1)."""
from __future__ import annotations

import httpx

from core.connectors.adzuna_connector import AdzunaConnector
from core.models.search_criteria import SearchCriteria


def _make_job(job_id: str) -> dict:
    return {
        "id": job_id,
        "title": "Python Developer",
        "company": {"display_name": "Acme"},
        "redirect_url": f"https://www.adzuna.com/jobs/details/{job_id}",
        "location": {"display_name": "Remote"},
        "description": "Build stuff.",
    }


def _connector_for(handler, **overrides) -> AdzunaConnector:
    transport = httpx.MockTransport(handler)
    kwargs = {"app_id": "app-id", "app_key": "app-key"}
    kwargs.update(overrides)
    return AdzunaConnector(
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        **kwargs,
    )


async def test_pagination_fetches_multiple_pages():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        count = 50 if call_count == 1 else 25
        return httpx.Response(
            200, json={"results": [_make_job(f"p{call_count}-{i}") for i in range(count)]}
        )

    connector = _connector_for(handler, max_results=75, page_size=50)
    jobs = await connector.search(SearchCriteria())
    assert call_count == 2
    assert len(jobs) == 75


async def test_pagination_stops_on_empty_page():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={"results": [_make_job("j1")]})
        return httpx.Response(200, json={"results": []})

    connector = _connector_for(handler, max_results=75, page_size=50)
    jobs = await connector.search(SearchCriteria())
    assert call_count == 2
    assert len(jobs) == 1


async def test_pagination_trims_to_max_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"results": [_make_job(f"j{i}") for i in range(50)]}
        )

    connector = _connector_for(handler, max_results=10, page_size=50)
    jobs = await connector.search(SearchCriteria())
    assert len(jobs) == 10


async def test_pagination_single_page_when_max_lte_page_size():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200, json={"results": [_make_job(f"j{i}") for i in range(20)]}
        )

    connector = _connector_for(handler, max_results=20, page_size=50)
    jobs = await connector.search(SearchCriteria())
    assert call_count == 1
    assert len(jobs) == 20
