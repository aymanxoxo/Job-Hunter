"""DuckDuckGo discovery connector (C-020, SDD §6.1).

Discovers real job postings from the open web using DuckDuckGo searches, then applies an
AI purification pass that filters noise and synthesises a company trust score before returning
structured Job objects to the pipeline.

No API keys or credentials required — DuckDuckGo is free and open. The ``ai_complete``
callable is injected by the runner from the active AI provider (``provider.complete``).

Pipeline inside ``search()``:
  1. AI generates DDG search queries from SearchCriteria (no site: restrictions).
  2. DDG executes queries; raw results collected.
  3. AI purifies: keep only actual job postings, extract company name.
  4. (Optional) Trust scoring: DDG trust searches → AI synthesises trust_score 0–100.
  5. Threshold filter: drop companies below trust_threshold when enabled.
  6. httpx fetches surviving URLs; AI extracts structured Job fields from page text.
  7. Return list[Job] with trust_score + trust_summary populated.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
import uuid
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import httpx

from core.connectors.base_connector import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

log = logging.getLogger(__name__)

_SAFE_URL_SCHEMES = frozenset({"http", "https"})

# Default ceiling on simultaneous network calls (page fetches, trust lookups) so a wide
# result set cannot fan out into hundreds of concurrent sockets/AI calls (C-073).
_DEFAULT_CONCURRENCY = 5


def _is_public_ip(ip: str) -> bool:
    """Return True only for a public IP literal — rejects private/loopback/link-local/etc."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _is_safe_url(url: str) -> bool:
    """Return True only for public http(s) URLs; block private/loopback/non-http targets."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in _SAFE_URL_SCHEMES:
        return False
    host = parsed.hostname
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host.lower() != "localhost"
    return _is_public_ip(host)


AiCompleteFn = Callable[[str], Awaitable[str]]
DdgSearchFn = Callable[[str, int], Awaitable[list[dict[str, str]]]]
HttpFetchFn = Callable[[str], Awaitable[str]]

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

_QUERY_PROMPT = """\
You are a job search expert. Given the following criteria, generate 3 concise DuckDuckGo search \
queries to find relevant job postings from any company's career site or job board.
Do NOT use "site:" restrictions — broad open-web coverage is the goal.
Return ONLY a JSON array of query strings, nothing else.

Titles: {titles}
Keywords: {keywords}
Locations: {locations}

Example: ["senior python developer remote jobs 2024", "python backend engineer careers apply now"]
"""

_PURIFY_PROMPT = """\
Filter the following web search results to keep only genuine job postings.
For each kept result, also extract the company name from the URL or title.
Return ONLY a JSON array. Each element: {{"url": "...", "title": "...", "company": "..."}}
Skip aggregator lists, salary guides, articles, or anything that is not a direct job posting.

Results:
{results_json}
"""

_TRUST_PROMPT = """\
Assess the trustworthiness of the following company as an employer and business.
Based on the search snippets below (from Glassdoor, Reddit, Trustpilot, etc.), assign a trust \
score 0–100 and write a one-sentence summary.
0 = scam/terrible, 60 = average/unknown, 100 = excellent employer reputation.

Company: {company}
Snippets:
{snippets}

Return ONLY valid JSON: {{"trust_score": <int 0-100>, "trust_summary": "<one sentence>"}}
"""

_EXTRACT_JOB_PROMPT = """\
Extract job details from the page text below. Return ONLY valid JSON with these fields:
title (str), company (str), location (str or null), description (str max 500 chars), \
salary_range (str or null).

Page URL: {url}
Page text:
{page_text}
"""


class DDGConnectorError(RuntimeError):
    """Raised for non-recoverable DDGConnector failures."""


class DDGConnector(BaseConnector):
    """Open-web job discovery via DuckDuckGo with AI purification and optional trust scoring."""

    name = "duckduckgo"
    auth_methods = ("none",)

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_results: int = 50,
        results_per_query: int = 10,
        trust_threshold: int = 60,
        trust_check_enabled: bool = True,
        max_concurrency: int = _DEFAULT_CONCURRENCY,
        ai_complete: AiCompleteFn | None = None,
        ddg_search_fn: DdgSearchFn | None = None,
        http_fetch_fn: HttpFetchFn | None = None,
        **_kw: Any,
    ) -> None:
        self.enabled = enabled
        self.max_results = max_results
        self.results_per_query = results_per_query
        self.trust_threshold = trust_threshold
        self.trust_check_enabled = trust_check_enabled
        self.max_concurrency = max(1, int(max_concurrency))
        self._ai_complete = ai_complete
        self._ddg_search: DdgSearchFn = ddg_search_fn or _real_ddg_search
        self._http_fetch: HttpFetchFn = http_fetch_fn or _real_http_fetch

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        if self._ai_complete is None:
            log.warning("DDGConnector: no ai_complete wired; returning empty results.")
            return []

        # 1. Generate search queries
        queries = await _generate_queries(criteria, self._ai_complete)
        if not queries:
            log.warning("DDGConnector: AI returned no search queries.")
            return []

        # 2. Execute DDG searches
        raw: list[dict[str, str]] = []
        for query in queries:
            try:
                results = await self._ddg_search(query, self.results_per_query)
                raw.extend(results)
            except Exception as exc:
                log.warning("DDGConnector: DDG search failed for %r: %s", query, exc)

        if not raw:
            return []

        # 3. AI purification — keep job postings, extract company names
        purified = await _purify_results(raw, self._ai_complete)
        if not purified:
            return []

        # Shared bound on concurrent network fan-out for trust lookups and page fetches.
        semaphore = asyncio.Semaphore(self.max_concurrency)

        # 4. Compute trust data once for all companies (when trust check enabled), concurrently.
        trust_map: dict[str, tuple[int, str | None]] = {}
        if self.trust_check_enabled:
            companies = list({item.get("company", "") for item in purified if item.get("company")})
            trust_map = await _score_companies_trust(
                companies, self._ddg_search, self._ai_complete, semaphore=semaphore
            )
            if self.trust_threshold > 0:
                purified = [
                    item for item in purified
                    if trust_map.get(item.get("company", ""), (50, None))[0] >= self.trust_threshold
                ]

        # 5. Fetch pages + extract Job fields, concurrently under the shared semaphore.
        safe_items = [item for item in purified if _is_safe_url(item.get("url", ""))]

        async def _fetch_and_extract(item: dict[str, str]) -> Job | None:
            url = item.get("url", "")
            async with semaphore:
                try:
                    page_text = await self._http_fetch(url)
                    job = await _extract_job(item, page_text, self._ai_complete)
                except Exception as exc:
                    log.warning("DDGConnector: failed to process %s: %s", url, exc)
                    return None
            if job is None:
                return None
            trust_score: int | None = None
            trust_summary: str | None = None
            if self.trust_check_enabled:
                company = item.get("company", "")
                if company and company in trust_map:
                    trust_score, trust_summary = trust_map[company]
            return job.model_copy(update={
                "trust_score": trust_score,
                "trust_summary": trust_summary,
            })

        results = await asyncio.gather(*(_fetch_and_extract(item) for item in safe_items))
        jobs = [job for job in results if job is not None]
        return jobs[: self.max_results]


# ---------------------------------------------------------------------------
# Pure helper functions (injectable / testable)
# ---------------------------------------------------------------------------

async def _generate_queries(criteria: SearchCriteria, ai_complete: AiCompleteFn) -> list[str]:
    prompt = _QUERY_PROMPT.format(
        titles=", ".join(criteria.titles) or "any",
        keywords=", ".join(criteria.keywords) or "any",
        locations=", ".join(criteria.locations) or "remote",
    )
    try:
        response = await ai_complete(prompt)
        queries = _loads(response)
        if isinstance(queries, list):
            return [q for q in queries if isinstance(q, str)]
    except Exception as exc:
        log.warning("DDGConnector: failed to parse query response: %s", exc)
    return []


async def _purify_results(
    results: list[dict[str, str]], ai_complete: AiCompleteFn
) -> list[dict[str, str]]:
    results_json = json.dumps(
        [{"url": r.get("href", ""), "title": r.get("title", ""), "snippet": r.get("body", "")}
         for r in results]
    )
    prompt = _PURIFY_PROMPT.format(results_json=results_json)
    try:
        response = await ai_complete(prompt)
        purified = _loads(response)
        if isinstance(purified, list):
            return [p for p in purified if isinstance(p, dict) and p.get("url")]
    except Exception as exc:
        log.warning("DDGConnector: failed to parse purification response: %s", exc)
    return []


async def _score_companies_trust(
    companies: list[str],
    ddg_search: DdgSearchFn,
    ai_complete: AiCompleteFn,
    *,
    semaphore: asyncio.Semaphore | None = None,
) -> dict[str, tuple[int, str | None]]:
    """Return per-company (trust_score, trust_summary) pairs, scored concurrently.

    A shared ``semaphore`` (from the caller) bounds the number of in-flight trust lookups;
    when omitted, one large enough to allow all companies through is created locally.
    """
    if not companies:
        return {}
    sem = semaphore or asyncio.Semaphore(len(companies))

    async def _one(company: str) -> tuple[str, tuple[int, str | None]]:
        async with sem:
            return company, await _score_one_company_trust(company, ddg_search, ai_complete)

    return dict(await asyncio.gather(*(_one(company) for company in companies)))


async def _score_one_company_trust(
    company: str,
    ddg_search: DdgSearchFn,
    ai_complete: AiCompleteFn,
) -> tuple[int, str | None]:
    """Score a single company's trust from its DDG snippets; defaults to (50, None)."""
    snippets = await _gather_trust_snippets(company, ddg_search)
    if not snippets:
        return (50, None)
    prompt = _TRUST_PROMPT.format(
        company=company,
        snippets="\n---\n".join(snippets[:6]),
    )
    try:
        response = await ai_complete(prompt)
        data = _loads(response)
        if isinstance(data, dict):
            return (int(data.get("trust_score", 50)), data.get("trust_summary") or None)
        return (50, None)
    except Exception:
        return (50, None)


async def _gather_trust_snippets(company: str, ddg_search: DdgSearchFn) -> list[str]:
    queries = [
        f"{company} glassdoor reviews",
        f"{company} site:reddit.com employer reviews",
        f"{company} site:trustpilot.com",
    ]
    snippets: list[str] = []
    for q in queries:
        try:
            results = await ddg_search(q, 3)
            snippets.extend(r.get("body", "") for r in results if r.get("body"))
        except Exception:
            pass
    return snippets


async def _extract_job(
    item: dict[str, str],
    page_text: str,
    ai_complete: AiCompleteFn,
) -> Job | None:
    prompt = _EXTRACT_JOB_PROMPT.format(
        url=item.get("url", ""),
        page_text=page_text[:3000],
    )
    try:
        response = await ai_complete(prompt)
        data = _loads(response)
        if not isinstance(data, dict):
            return None
        title = data.get("title") or item.get("title") or "Unknown"
        company = data.get("company") or item.get("company") or "Unknown"
        return Job(
            id=f"ddg-{uuid.uuid4()}",
            title=title,
            company=company,
            url=item.get("url", ""),
            source=DDGConnector.name,
            location=data.get("location"),
            description=data.get("description"),
            salary_range=data.get("salary_range"),
        )
    except Exception as exc:
        log.warning("DDGConnector: job extraction failed: %s", exc)
        return None


def _loads(text: str) -> Any:
    """Parse JSON from LLM output, stripping markdown fences if present."""
    match = _FENCE_RE.search(text)
    candidate = match.group(1) if match else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        try:
            return json.loads(candidate.strip())
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------------------
# Real (network) implementations — replaced by injected fns in tests
# ---------------------------------------------------------------------------

async def _real_ddg_search(query: str, max_results: int) -> list[dict[str, str]]:
    """Execute a DDG text search (sync library run in thread executor)."""
    from duckduckgo_search import DDGS  # noqa: PLC0415

    def _sync() -> list[dict]:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    return await asyncio.to_thread(_sync)


def _resolve_public_ip(host: str, resolver: Callable[..., list] | None = None) -> str:
    """Resolve ``host`` and return a single public IP, or raise on any non-public answer.

    This closes the DNS-rebind window: ``_is_safe_url`` only vets the *literal* host, so a
    hostname that resolves to a private/loopback address (or rebinds to one between checks)
    would otherwise slip through. Every resolved address must be public or the fetch is refused.
    """
    resolve = resolver or socket.getaddrinfo
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if _is_public_ip(host):
            return host
        raise DDGConnectorError(f"refusing to fetch non-public address: {host}")
    try:
        infos = resolve(host, None)
    except OSError as exc:
        raise DDGConnectorError(f"could not resolve host {host!r}: {exc}") from exc
    ips = [info[4][0] for info in infos]
    if not ips:
        raise DDGConnectorError(f"host {host!r} did not resolve to any address")
    for ip in ips:
        if not _is_public_ip(ip):
            raise DDGConnectorError(
                f"refusing to fetch {host!r}: resolves to non-public address {ip}"
            )
    return ips[0]


async def _real_http_fetch(url: str) -> str:
    """Fetch a URL with the connection pinned to a re-validated public IP (DNS-rebind guard).

    Redirects are not followed: a redirect target would be resolved by httpx outside this
    guard, re-opening the SSRF/rebind hole.
    """
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise DDGConnectorError(f"URL has no host: {url!r}")
    ip = await asyncio.to_thread(_resolve_public_ip, host)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    netloc = f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}"
    pinned_url = parsed._replace(netloc=netloc).geturl()
    host_header = host if port in (80, 443) else f"{host}:{port}"
    async with httpx.AsyncClient(follow_redirects=False, timeout=15.0) as client:
        response = await client.get(
            pinned_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; JobHunter/1.0)",
                "Host": host_header,
            },
            extensions={"sni_hostname": host},
        )
        response.raise_for_status()
        return response.text
