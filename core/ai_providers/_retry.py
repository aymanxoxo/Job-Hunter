"""Shared retry handling for provider HTTP calls (C-054/C-064, SDD §7)."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TypeVar

import httpx

T = TypeVar("T")
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


async def http_call_with_retry(
    fn: Callable[[], Awaitable[httpx.Response]],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> httpx.Response:
    """Call fn(), retrying on transient network errors and retryable HTTP status codes.

    Retries on: NetworkError, TimeoutException, and status codes 429/500/502/503/504.
    Raises immediately on all other errors (4xx auth failures, bad requests, etc.).
    Delay between attempts: Retry-After when provided, else base_delay * 2^attempt.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    for attempt in range(max_attempts):
        try:
            response = await fn()
            if response.status_code in _RETRYABLE_STATUS:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(_retry_delay(response, attempt, base_delay))
                    continue
            return response
        except (httpx.NetworkError, httpx.TimeoutException):
            if attempt < max_attempts - 1:
                await asyncio.sleep(base_delay * (2**attempt))
                continue
            raise
    raise RuntimeError("unreachable retry state")


def _retry_delay(response: httpx.Response, attempt: int, base_delay: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        parsed = _parse_retry_after(retry_after)
        if parsed is not None:
            return parsed
    return base_delay * (2**attempt)


def _parse_retry_after(value: str) -> float | None:
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
