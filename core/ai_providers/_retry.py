"""Shared exponential-backoff retry for provider HTTP calls (C-054, SDD §7)."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
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
    Delay between attempts: base_delay * 2^attempt (1 s, 2 s on a 3-attempt sequence).
    """
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            response = await fn()
            if response.status_code in _RETRYABLE_STATUS:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(base_delay * (2**attempt))
                    continue
            return response
        except (httpx.NetworkError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                await asyncio.sleep(base_delay * (2**attempt))
    if last_exc is not None:
        raise last_exc
    # max_attempts exhausted on retryable status — return the last response for
    # the caller to raise_for_status() so the error propagates normally
    return response  # type: ignore[return-value]  # assigned in last loop iteration
