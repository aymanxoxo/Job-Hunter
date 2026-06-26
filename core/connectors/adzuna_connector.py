"""Adzuna job-search connector (C-051, hardened C-065)."""
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any

import httpx
from pydantic import ValidationError

from core.connectors.base_connector import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

ADZUNA_ENDPOINT_TEMPLATE = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
DEFAULT_ADZUNA_COUNTRY = "us"
DEFAULT_ADZUNA_TIMEOUT = 30.0
DEFAULT_ADZUNA_PAGE_SIZE = 50
DEFAULT_ADZUNA_APP_ID_ENV = "ADZUNA_APP_ID"
DEFAULT_ADZUNA_APP_KEY_ENV = "ADZUNA_APP_KEY"

_RETRYABLE_CODES = frozenset({429, 500, 502, 503, 504})
log = logging.getLogger(__name__)

ClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]


class AdzunaConnectorError(RuntimeError):
    """Raised when Adzuna search cannot return usable results."""


class AdzunaConnector(BaseConnector):
    """Connector backed by Adzuna's sanctioned jobs API."""

    name = "adzuna"
    auth_methods = ("api_key",)

    def __init__(
        self,
        *,
        app_id: str | None = None,
        app_key: str | None = None,
        app_id_env: str = DEFAULT_ADZUNA_APP_ID_ENV,
        app_key_env: str = DEFAULT_ADZUNA_APP_KEY_ENV,
        country: str = DEFAULT_ADZUNA_COUNTRY,
        endpoint_template: str = ADZUNA_ENDPOINT_TEMPLATE,
        timeout: float = DEFAULT_ADZUNA_TIMEOUT,
        page_size: int = DEFAULT_ADZUNA_PAGE_SIZE,
        client_factory: ClientFactory | None = None,
        enabled: bool = True,
        max_results: int = 50,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        max_attempts: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        self.app_id = app_id
        self.app_key = app_key
        self.app_id_env = app_id_env
        self.app_key_env = app_key_env
        self.country = country
        self.endpoint_template = endpoint_template
        self.timeout = timeout
        self.page_size = page_size
        self._client_factory = client_factory or self._default_client_factory
        self.enabled = enabled
        self.max_results = max_results
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    @classmethod
    def auth_config_kwargs(cls, auth: Any) -> dict[str, Any]:
        return {
            "app_id_env": getattr(auth, "adzuna_app_id_env", None),
            "app_key_env": getattr(auth, "adzuna_app_key_env", None),
        }

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        """Search Adzuna and return raw unscored jobs, paginating until max_results reached."""
        app_id, app_key = self._credentials()
        collected: list[Job] = []
        page = 1
        # Credentials go in Authorization header to keep them out of URL query strings
        # (URL params appear in proxy logs and server access logs; Basic Auth does not).
        auth = (app_id, app_key)
        async with self._client_factory() as client:
            while len(collected) < self.max_results:
                remaining = self.max_results - len(collected)
                page_size = min(self.page_size, remaining)
                params = _params_for(criteria, page_size=page_size)
                endpoint = self.endpoint_template.format(country=self.country, page=page)
                response = await _adzuna_get(
                    client, endpoint,
                    auth=auth, params=params, timeout=self.timeout,
                    max_attempts=self.max_attempts, base_delay=self.base_delay,
                )
                if response.status_code >= 400:
                    raise AdzunaConnectorError(
                        f"Adzuna search failed with HTTP {response.status_code}."
                    )
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise AdzunaConnectorError(
                        "Adzuna response body was not valid JSON."
                    ) from exc
                results = payload.get("results") if isinstance(payload, dict) else None
                if not isinstance(results, list):
                    raise AdzunaConnectorError(
                        "Adzuna response JSON must include a results list."
                    )
                page_jobs: list[Job] = []
                for item in results:
                    job = _job_from_result(item)
                    if job is not None:
                        page_jobs.append(job)
                    else:
                        log.debug(
                            "adzuna: dropped malformed result record id=%s",
                            item.get("id") if isinstance(item, dict) else "?",
                        )
                if not page_jobs:
                    break
                collected.extend(page_jobs)
                page += 1
        return collected[: self.max_results]

    def _credentials(self) -> tuple[str, str]:
        app_id = self.app_id or os.environ.get(self.app_id_env)
        app_key = self.app_key or os.environ.get(self.app_key_env)
        if not app_id or not app_key:
            raise AdzunaConnectorError(
                f"Missing Adzuna credentials; set {self.app_id_env} and {self.app_key_env}."
            )
        return app_id, app_key

    def _default_client_factory(self) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        return httpx.AsyncClient()


async def _adzuna_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    auth: tuple[str, str],
    params: dict,
    timeout: float,
    max_attempts: int,
    base_delay: float,
) -> httpx.Response:
    """GET with exponential-backoff retry on transient network errors and 429/5xx."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = await client.get(url, auth=auth, params=params, timeout=timeout)
            if response.status_code not in _RETRYABLE_CODES or attempt == max_attempts - 1:
                return response
            await asyncio.sleep(base_delay * (2 ** attempt))
        except (httpx.NetworkError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(base_delay * (2 ** attempt))
    raise AdzunaConnectorError("unreachable retry state") from last_exc


def _params_for(
    criteria: SearchCriteria, *, page_size: int
) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "results_per_page": page_size,
        "content-type": "application/json",
    }
    what = " ".join((*criteria.titles, *criteria.keywords)).strip()
    if what:
        params["what"] = what
    what_exclude = " ".join(criteria.exclude_keywords).strip()
    if what_exclude:
        params["what_exclude"] = what_exclude
    where = " ".join(criteria.locations).strip()
    if where:
        params["where"] = where
    return params


def _job_from_result(item: Any) -> Job | None:
    if not isinstance(item, dict):
        return None
    company = item.get("company") if isinstance(item.get("company"), dict) else {}
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    data = {
        "id": f"adzuna-{item.get('id')}",
        "title": item.get("title"),
        "company": company.get("display_name"),
        "url": item.get("redirect_url"),
        "source": AdzunaConnector.name,
        "location": location.get("display_name"),
        "description": item.get("description"),
        "salary_range": _salary_range(item.get("salary_min"), item.get("salary_max")),
        "posted_date": _posted_date(item.get("created")),
        "raw": item,
    }
    try:
        return Job(**data)
    except ValidationError:
        return None


def _salary_range(salary_min: Any, salary_max: Any) -> str | None:
    if salary_min is None and salary_max is None:
        return None
    if salary_min is None:
        return f"Up to {_format_salary(salary_max)}"
    if salary_max is None:
        return f"From {_format_salary(salary_min)}"
    return f"{_format_salary(salary_min)} - {_format_salary(salary_max)}"


def _format_salary(value: Any) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _posted_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
