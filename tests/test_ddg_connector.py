"""C-020 — DDGConnector tests.

All network I/O (DDG searches, HTTP fetches, AI completions) is injected as async callables
so no real network traffic occurs.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from core.connectors.duckduckgo_connector import (
    DDGConnector,
    DDGConnectorError,
    _extract_job,
    _gather_trust_snippets,
    _generate_queries,
    _is_public_ip,
    _is_safe_url,
    _loads,
    _purify_results,
    _real_http_fetch,
    _resolve_public_ip,
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
# _is_safe_url — SSRF guard
# ---------------------------------------------------------------------------

def test_is_safe_url_allows_public_http_and_https():
    assert _is_safe_url("https://example.com/jobs/1")
    assert _is_safe_url("http://careers.company.co.uk/apply")


def test_is_safe_url_blocks_non_http_schemes():
    assert not _is_safe_url("javascript:alert(1)")
    assert not _is_safe_url("file:///etc/passwd")
    assert not _is_safe_url("ftp://files.example.com/data")


def test_is_safe_url_blocks_private_and_loopback_ips():
    assert not _is_safe_url("http://192.168.1.1/admin")
    assert not _is_safe_url("http://10.0.0.1/secret")
    assert not _is_safe_url("http://172.16.0.1/internal")
    assert not _is_safe_url("http://127.0.0.1:6379/")
    assert not _is_safe_url("http://localhost/health")


async def test_search_skips_private_ip_urls():
    """Purified URLs pointing at RFC1918 addresses must not be fetched."""
    fetched: list[str] = []

    async def _http(url: str) -> str:
        fetched.append(url)
        return "<html>job</html>"

    async def _ai(prompt: str) -> str:
        if "DuckDuckGo" in prompt or "queries" in prompt.lower():
            return json.dumps(["python jobs"])
        if "genuine" in prompt.lower() or "filter" in prompt.lower():
            return json.dumps([
                {"url": "http://192.168.1.100/jobs", "title": "Dev", "company": "Co"}
            ])
        return json.dumps({"title": "Dev", "company": "Co", "location": None,
                           "description": "x", "salary_range": None})

    async def _ddg(query: str, n: int) -> list[dict]:
        return [{"href": "http://192.168.1.100/jobs", "title": "Dev", "body": "x"}]

    connector = DDGConnector(
        trust_check_enabled=False,
        ai_complete=_ai,
        ddg_search_fn=_ddg,
        http_fetch_fn=_http,
    )
    jobs = await connector.search(_CRITERIA)

    assert fetched == []
    assert jobs == []


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
    score, summary = scores["Acme"]
    assert score == 82
    assert summary == "Highly rated"


async def test_score_companies_trust_defaults_to_50_when_no_snippets():
    scores = await _score_companies_trust(["Unknown Co"], _ddg_empty, _ai_returns({}))
    score, summary = scores["Unknown Co"]
    assert score == 50
    assert summary is None


async def test_score_companies_trust_defaults_to_50_on_bad_ai():
    async def _ddg(query: str, n: int) -> list[dict]:
        return [{"body": "some snippet"}]

    async def _bad_ai(prompt: str) -> str:
        return "not json"

    scores = await _score_companies_trust(["Acme"], _ddg, _bad_ai)
    score, summary = scores["Acme"]
    assert score == 50
    assert summary is None


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


async def test_search_trust_summary_populated_from_ai():
    """trust_summary on returned jobs must reflect the AI assessment, not always be None."""
    async def _ai(prompt: str) -> str:
        if "DuckDuckGo" in prompt or "queries" in prompt.lower():
            return json.dumps(["python jobs"])
        if "genuine" in prompt.lower() or "filter" in prompt.lower():
            return json.dumps([{"url": "https://goodco.com/job", "title": "Dev",
                                "company": "GoodCo"}])
        if "trustworthy" in prompt.lower() or "trust score" in prompt.lower() \
                or "glassdoor" in prompt.lower() or "trustpilot" in prompt.lower():
            return json.dumps({"trust_score": 85, "trust_summary": "Excellent employer"})
        return json.dumps({"title": "Dev", "company": "GoodCo", "location": "Remote",
                           "description": "coding", "salary_range": None})

    async def _ddg(query: str, n: int) -> list[dict]:
        if any(kw in query for kw in ("glassdoor", "reddit", "trustpilot")):
            return [{"body": "Great reviews, very positive"}]
        return [{"href": "https://goodco.com/job", "title": "Dev", "body": "Apply now"}]

    connector = DDGConnector(
        trust_threshold=60,
        trust_check_enabled=True,
        ai_complete=_ai,
        ddg_search_fn=_ddg,
        http_fetch_fn=_http_hello,
    )
    jobs = await connector.search(_CRITERIA)
    assert len(jobs) == 1
    assert jobs[0].trust_score == 85
    assert jobs[0].trust_summary == "Excellent employer"


# ---------------------------------------------------------------------------
# C-073 — DNS-rebind guard (_is_public_ip / _resolve_public_ip / _real_http_fetch)
# ---------------------------------------------------------------------------

def _addrinfo(*ips: str) -> callable:
    """Return a getaddrinfo-shaped resolver stub yielding the given IPs."""
    def _resolve(host, *args, **kwargs):
        return [(2, 1, 6, "", (ip, 0)) for ip in ips]
    return _resolve


def test_is_public_ip_distinguishes_public_from_private():
    assert _is_public_ip("93.184.216.34")
    assert not _is_public_ip("192.168.0.1")
    assert not _is_public_ip("127.0.0.1")
    assert not _is_public_ip("169.254.169.254")  # cloud metadata link-local
    assert not _is_public_ip("0.0.0.0")
    assert not _is_public_ip("not-an-ip")


def test_resolve_public_ip_returns_public_resolution():
    ip = _resolve_public_ip("example.com", resolver=_addrinfo("93.184.216.34"))
    assert ip == "93.184.216.34"


def test_resolve_public_ip_rejects_rebind_to_private_address():
    """A hostname that resolves to an RFC1918 address must be refused (DNS rebind)."""
    with pytest.raises(DDGConnectorError, match="non-public"):
        _resolve_public_ip("evil.example.com", resolver=_addrinfo("10.0.0.5"))


def test_resolve_public_ip_rejects_when_any_address_is_private():
    """If round-robin DNS mixes a public and a private answer, refuse the lot."""
    with pytest.raises(DDGConnectorError, match="non-public"):
        _resolve_public_ip(
            "mixed.example.com", resolver=_addrinfo("93.184.216.34", "169.254.169.254")
        )


def test_resolve_public_ip_validates_ip_literals_directly():
    assert _resolve_public_ip("93.184.216.34", resolver=_addrinfo()) == "93.184.216.34"
    with pytest.raises(DDGConnectorError, match="non-public"):
        _resolve_public_ip("127.0.0.1", resolver=_addrinfo())


def test_resolve_public_ip_raises_on_resolution_failure():
    def _boom(host, *args, **kwargs):
        raise OSError("name or service not known")

    with pytest.raises(DDGConnectorError, match="could not resolve"):
        _resolve_public_ip("nope.invalid", resolver=_boom)


async def test_real_http_fetch_rejects_rebind_before_any_network(monkeypatch):
    """_real_http_fetch must raise (no HTTP) when the host resolves to a private address."""
    monkeypatch.setattr(
        "core.connectors.duckduckgo_connector.socket.getaddrinfo",
        _addrinfo("192.168.1.50"),
    )

    async def _boom_client(*args, **kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("HTTP request attempted despite private rebind")

    monkeypatch.setattr(
        "core.connectors.duckduckgo_connector.httpx.AsyncClient", _boom_client
    )

    with pytest.raises(DDGConnectorError, match="non-public"):
        await _real_http_fetch("https://evil.example.com/job")


# ---------------------------------------------------------------------------
# C-073 — bounded concurrency
# ---------------------------------------------------------------------------

async def test_score_companies_trust_returns_empty_for_no_companies():
    assert await _score_companies_trust([], _ddg_empty, _ai_returns({})) == {}


async def test_search_bounds_page_fetch_concurrency():
    """No more than max_concurrency page fetches run at once; all still complete."""
    items = [
        {"url": f"https://co.com/job/{i}", "title": f"Dev {i}", "company": "Co"}
        for i in range(12)
    ]
    live = {"now": 0, "peak": 0}

    async def _http(url: str) -> str:
        live["now"] += 1
        live["peak"] = max(live["peak"], live["now"])
        await asyncio.sleep(0.01)  # force overlap
        live["now"] -= 1
        return "<html>job</html>"

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
        max_concurrency=3,
        trust_check_enabled=False,
        ai_complete=_ai,
        ddg_search_fn=_ddg,
        http_fetch_fn=_http,
    )
    jobs = await connector.search(_CRITERIA)
    assert len(jobs) == 12
    assert live["peak"] == 3  # saturated the bound but never exceeded it


async def test_search_bounds_trust_scoring_concurrency():
    """Per-company trust scoring also respects the shared concurrency bound."""
    companies = [f"Company{i}" for i in range(10)]
    items = [
        {"url": f"https://co{i}.com/job", "title": "Dev", "company": companies[i]}
        for i in range(10)
    ]
    live = {"now": 0, "peak": 0}

    async def _ddg(query: str, n: int) -> list[dict]:
        if any(kw in query for kw in ("glassdoor", "reddit", "trustpilot")):
            live["now"] += 1
            live["peak"] = max(live["peak"], live["now"])
            await asyncio.sleep(0.01)
            live["now"] -= 1
            return [{"body": "reviews"}]
        return [{"href": it["url"], "title": "Dev", "body": ""} for it in items]

    async def _ai(prompt: str) -> str:
        if "DuckDuckGo" in prompt or "queries" in prompt.lower():
            return json.dumps(["python jobs"])
        if "genuine" in prompt.lower() or "filter" in prompt.lower():
            return json.dumps(items)
        if "trustworthy" in prompt.lower() or "trust score" in prompt.lower():
            return json.dumps({"trust_score": 90, "trust_summary": "ok"})
        return json.dumps({"title": "Dev", "company": "Co", "location": None,
                           "description": "code", "salary_range": None})

    connector = DDGConnector(
        max_concurrency=2,
        trust_threshold=0,  # keep all, isolate the concurrency assertion
        trust_check_enabled=True,
        ai_complete=_ai,
        ddg_search_fn=_ddg,
        http_fetch_fn=_http_hello,
    )
    await connector.search(_CRITERIA)
    assert live["peak"] <= 2 and live["peak"] >= 1
