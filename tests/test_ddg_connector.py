"""C-020 — DDGConnector tests.

All network I/O (DDG searches, HTTP fetches, AI completions) is injected as async callables
so no real network traffic occurs.
"""
from __future__ import annotations

import json

from core.connectors.duckduckgo_connector import (
    DDGConnector,
    _extract_job,
    _gather_trust_snippets,
    _generate_queries,
    _loads,
    _purify_results,
    _score_companies_trust,
)
from core.models.search_criteria import SearchCriteria

# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

_CRITERIA = SearchCriteria(
    keywords=("python", "django"),
    titles=("backend engineer",),
    locations=("remote",),
    raw_profile="senior python dev",
)


def _ai_returns(payload) -> callable:
    """Return an ai_complete stub that always returns the JSON-serialised payload."""
    async def _fn(prompt: str) -> str:
        return json.dumps(payload)
    return _fn


async def _ddg_empty(query: str, n: int) -> list[dict]:
    return []


async def _http_hello(url: str) -> str:
    return "<html><body>Python Engineer at Acme Corp. Apply now.</body></html>"


# ---------------------------------------------------------------------------
# _loads — fence stripping and JSON parsing
# ---------------------------------------------------------------------------

def test_loads_plain_json():
    assert _loads('{"a": 1}') == {"a": 1}


def test_loads_fenced_json():
    assert _loads('```json\n["x", "y"]\n```') == ["x", "y"]


def test_loads_invalid_returns_none():
    assert _loads("not json at all") is None


# ---------------------------------------------------------------------------
# _generate_queries
# ---------------------------------------------------------------------------

async def test_generate_queries_returns_list_from_ai():
    queries = await _generate_queries(
        _CRITERIA, _ai_returns(["python jobs remote", "django backend engineer careers"])
    )
    assert queries == ["python jobs remote", "django backend engineer careers"]


async def test_generate_queries_filters_non_strings():
    queries = await _generate_queries(_CRITERIA, _ai_returns(["ok", 42, None, "also ok"]))
    assert queries == ["ok", "also ok"]


async def test_generate_queries_returns_empty_on_bad_ai_response():
    async def _bad(prompt: str) -> str:
        return "not json"
    queries = await _generate_queries(_CRITERIA, _bad)
    assert queries == []


# ---------------------------------------------------------------------------
# _purify_results
# ---------------------------------------------------------------------------

async def test_purify_results_keeps_job_postings():
    raw = [{"href": "https://example.com/jobs/1", "title": "Python Dev", "body": "..."}]
    purified = await _purify_results(
        raw,
        _ai_returns([{"url": "https://example.com/jobs/1", "title": "Python Dev",
                      "company": "Acme"}]),
    )
    assert len(purified) == 1
    assert purified[0]["company"] == "Acme"


async def test_purify_results_drops_entries_without_url():
    async def _ai(prompt: str) -> str:
        return json.dumps([{"title": "No URL here", "company": "X"}])
    purified = await _purify_results([{"href": "", "title": "x"}], _ai)
    assert purified == []


async def test_purify_results_returns_empty_on_bad_ai():
    async def _bad(prompt: str) -> str:
        return "garbage"
    purified = await _purify_results([{"href": "http://x.com"}], _bad)
    assert purified == []


# ---------------------------------------------------------------------------
# _gather_trust_snippets
# ---------------------------------------------------------------------------

async def test_gather_trust_snippets_collects_from_multiple_queries():
    call_count = {"n": 0}

    async def _ddg(query: str, n: int) -> list[dict]:
        call_count["n"] += 1
        return [{"body": f"snippet for {query}"}]

    snippets = await _gather_trust_snippets("Acme Corp", _ddg)
    assert len(snippets) == 3  # 3 queries × 1 result each
    assert call_count["n"] == 3


async def test_gather_trust_snippets_tolerates_ddg_failure():
    async def _boom(query: str, n: int) -> list[dict]:
        raise RuntimeError("network error")

    snippets = await _gather_trust_snippets("Acme Corp", _boom)
    assert snippets == []


# ---------------------------------------------------------------------------
# _score_companies_trust
# ---------------------------------------------------------------------------

async def test_score_companies_trust_returns_ai_score():
    async def _ddg(query: str, n: int) -> list[dict]:
        return [{"body": "Great employer, positive reviews"}]

    scores = await _score_companies_trust(
        ["Acme"],
        _ddg,
        _ai_returns({"trust_score": 82, "trust_summary": "Highly rated"}),
    )
    assert scores["Acme"] == 82


async def test_score_companies_trust_defaults_to_50_when_no_snippets():
    scores = await _score_companies_trust(["Unknown Co"], _ddg_empty, _ai_returns({}))
    assert scores["Unknown Co"] == 50


async def test_score_companies_trust_defaults_to_50_on_bad_ai():
    async def _ddg(query: str, n: int) -> list[dict]:
        return [{"body": "some snippet"}]

    async def _bad_ai(prompt: str) -> str:
        return "not json"

    scores = await _score_companies_trust(["Acme"], _ddg, _bad_ai)
    assert scores["Acme"] == 50


# ---------------------------------------------------------------------------
# _extract_job
# ---------------------------------------------------------------------------

async def test_extract_job_returns_job_with_fields():
    item = {"url": "https://example.com/job/1", "company": "Acme"}
    job = await _extract_job(
        item,
        "<html>Python engineer role at Acme</html>",
        _ai_returns({
            "title": "Python Engineer",
            "company": "Acme Corp",
            "location": "Remote",
            "description": "Build great things",
            "salary_range": "$100k",
        }),
    )
    assert job is not None
    assert job.title == "Python Engineer"
    assert job.company == "Acme Corp"
    assert job.location == "Remote"
    assert job.url == "https://example.com/job/1"
    assert job.source == "duckduckgo"


async def test_extract_job_falls_back_to_item_title_and_company_on_empty_ai_fields():
    item = {"url": "https://example.com/job/2", "title": "Dev Role", "company": "FallbackCo"}
    job = await _extract_job(
        item,
        "some page text",
        _ai_returns({"title": "", "company": ""}),
    )
    assert job is not None
    assert job.title == "Dev Role"
    assert job.company == "FallbackCo"


async def test_extract_job_returns_none_on_bad_ai():
    async def _bad(prompt: str) -> str:
        return "not json"

    job = await _extract_job({"url": "https://x.com"}, "text", _bad)
    assert job is None


# ---------------------------------------------------------------------------
# DDGConnector.search — integration
# ---------------------------------------------------------------------------

async def test_search_returns_empty_when_no_ai_complete():
    connector = DDGConnector()
    jobs = await connector.search(_CRITERIA)
    assert jobs == []


async def test_search_returns_empty_when_ai_returns_no_queries():
    connector = DDGConnector(ai_complete=_ai_returns([]))
    jobs = await connector.search(_CRITERIA)
    assert jobs == []


async def test_search_returns_empty_when_ddg_finds_nothing():
    connector = DDGConnector(
        ai_complete=_ai_returns(["python jobs"]),
        ddg_search_fn=_ddg_empty,
    )
    jobs = await connector.search(_CRITERIA)
    assert jobs == []


async def test_search_trust_threshold_excludes_low_trust_companies():
    """Companies scoring below trust_threshold are excluded."""
    purified_item = {"url": "https://sketchyco.com/job", "title": "Job", "company": "SketchyCo"}

    ai_calls: list[str] = []

    async def _ai(prompt: str) -> str:
        ai_calls.append(prompt)
        if "generate" in prompt.lower() or "queries" in prompt.lower() or "DuckDuckGo" in prompt:
            return json.dumps(["python job"])
        if "filter" in prompt.lower() or "purify" in prompt.lower() or "genuine" in prompt.lower():
            return json.dumps([purified_item])
        if ("trustworthy" in prompt.lower() or "trust score" in prompt.lower()
                or "glassdoor" in prompt.lower()):
            return json.dumps({"trust_score": 20, "trust_summary": "Many complaints"})
        # job extraction
        return json.dumps({"title": "Dev", "company": "SketchyCo", "location": None,
                           "description": "job", "salary_range": None})

    async def _ddg(query: str, n: int) -> list[dict]:
        if "glassdoor" in query or "reddit" in query or "trustpilot" in query:
            return [{"body": "Bad reviews everywhere"}]
        return [{"href": "https://sketchyco.com/job", "title": "Job", "body": "Apply here"}]

    connector = DDGConnector(
        trust_threshold=60,
        trust_check_enabled=True,
        ai_complete=_ai,
        ddg_search_fn=_ddg,
        http_fetch_fn=_http_hello,
    )
    jobs = await connector.search(_CRITERIA)
    # SketchyCo got trust_score=20, below threshold=60 → excluded
    assert jobs == []


async def test_search_trust_check_disabled_skips_trust_scoring():
    """With trust_check_enabled=False, all companies pass regardless of reputation."""
    async def _ai(prompt: str) -> str:
        if "DuckDuckGo" in prompt or "queries" in prompt.lower():
            return json.dumps(["python remote jobs"])
        if "genuine" in prompt.lower() or "filter" in prompt.lower():
            return json.dumps([{"url": "https://co.com/job", "title": "Dev",
                                "company": "AnyCompany"}])
        return json.dumps({"title": "Dev", "company": "AnyCompany", "location": "Remote",
                           "description": "coding", "salary_range": None})

    async def _ddg(query: str, n: int) -> list[dict]:
        return [{"href": "https://co.com/job", "title": "Dev", "body": "Apply now"}]

    connector = DDGConnector(
        trust_check_enabled=False,
        ai_complete=_ai,
        ddg_search_fn=_ddg,
        http_fetch_fn=_http_hello,
    )
    jobs = await connector.search(_CRITERIA)
    assert len(jobs) == 1
    assert jobs[0].company == "AnyCompany"
    assert jobs[0].trust_score is None


async def test_search_respects_max_results():
    """Connector stops adding jobs once max_results is reached."""
    items = [
        {"url": f"https://co.com/job/{i}", "title": f"Dev {i}", "company": "Co"}
        for i in range(10)
    ]

    async def _ai(prompt: str) -> str:
        if "DuckDuckGo" in prompt or "queries" in prompt.lower():
            return json.dumps(["python jobs"])
        if "genuine" in prompt.lower() or "filter" in prompt.lower():
            return json.dumps(items)
        return json.dumps({"title": "Dev", "company": "Co", "location": None,
                           "description": "code", "salary_range": None})

    async def _ddg(query: str, n: int) -> list[dict]:
        return [{"href": it["url"], "title": it["title"], "body": ""} for it in items]

    connector = DDGConnector(
        max_results=3,
        trust_check_enabled=False,
        ai_complete=_ai,
        ddg_search_fn=_ddg,
        http_fetch_fn=_http_hello,
    )
    jobs = await connector.search(_CRITERIA)
    assert len(jobs) == 3


async def test_search_job_source_is_duckduckgo():
    async def _ai(prompt: str) -> str:
        if "DuckDuckGo" in prompt or "queries" in prompt.lower():
            return json.dumps(["python jobs"])
        if "genuine" in prompt.lower() or "filter" in prompt.lower():
            return json.dumps([{"url": "https://co.com/job", "title": "Dev", "company": "Co"}])
        return json.dumps({"title": "Dev", "company": "Co", "location": None,
                           "description": "x", "salary_range": None})

    async def _ddg(query: str, n: int) -> list[dict]:
        return [{"href": "https://co.com/job", "title": "Dev", "body": "x"}]

    connector = DDGConnector(
        trust_check_enabled=False,
        ai_complete=_ai,
        ddg_search_fn=_ddg,
        http_fetch_fn=_http_hello,
    )
    jobs = await connector.search(_CRITERIA)
    assert jobs and jobs[0].source == "duckduckgo"
