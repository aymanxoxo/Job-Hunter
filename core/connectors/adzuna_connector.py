"""Adzuna job-search connector (C-051)."""
from __future__ import annotations

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

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        """Search Adzuna and return raw unscored jobs."""
        app_id, app_key = self._credentials()
        effective_page = min(self.page_size, self.max_results)
        params = _params_for(criteria, app_id=app_id, app_key=app_key, page_size=effective_page)
        endpoint = self.endpoint_template.format(country=self.country, page=1)
        async with self._client_factory() as client:
            response = await client.get(endpoint, params=params, timeout=self.timeout)
        if response.status_code >= 400:
            raise AdzunaConnectorError(f"Adzuna search failed with HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AdzunaConnectorError("Adzuna response body was not valid JSON.") from exc
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise AdzunaConnectorError("Adzuna response JSON must include a results list.")
        return [job for item in results if (job := _job_from_result(item)) is not None]

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


def _params_for(
    criteria: SearchCriteria, *, app_id: str, app_key: str, page_size: int
) -> dict[str, str | int]:
    max_results = min(criteria.max_results, page_size)
    params: dict[str, str | int] = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": max_results,
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
