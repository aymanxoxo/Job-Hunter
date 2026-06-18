"""Structured, trace-friendly logging for JobHunter (ADR-010, dev plan §6).

JSON-line logs go to **stderr only** — stdout is the Tauri sidecar IPC channel, so a stray
stdout log would corrupt it. Every line carries bound context (e.g. ``run_id``, ``component``).
Secret-looking keys are redacted. Pure formatting/redaction live in module-level functions; the
only side effect is writing a line to a stream (default ``sys.stderr``), injectable for tests.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from collections.abc import Callable
from typing import Any, TextIO

REDACTED = "***REDACTED***"
_SECRET_HINTS = (
    "token", "api_key", "apikey", "password", "secret",
    "authorization", "cookie", "credential", "client_secret",
)


def new_run_id() -> str:
    """A fresh correlation id for one pipeline run (32-char hex)."""
    return uuid.uuid4().hex


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(hint in lowered for hint in _SECRET_HINTS)


def redact(value: Any) -> Any:
    """Pure: mask values under secret-looking keys, recursively; non-secret values pass through."""
    if isinstance(value, dict):
        return {k: (REDACTED if _is_secret_key(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def format_record(
    level: str,
    name: str,
    message: str,
    context: dict[str, Any] | None,
    *,
    ts: str | None = None,
) -> str:
    """Pure: build one JSON log line. ``ts`` is injectable for deterministic tests."""
    record: dict[str, Any] = {
        "ts": ts if ts is not None else _now_iso(),
        "level": level,
        "logger": name,
        "msg": message,
    }
    if context:
        record.update(redact(context))
    return json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)


class Logger:
    """A context-bound logger; ``bind()`` returns a new Logger (immutable). Writes to stderr."""

    def __init__(
        self,
        name: str,
        context: dict[str, Any] | None = None,
        stream: TextIO | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.name = name
        self._ctx: dict[str, Any] = dict(context or {})
        self._stream: TextIO = stream if stream is not None else sys.stderr
        self._clock = clock

    def bind(self, **fields: Any) -> Logger:
        return Logger(self.name, {**self._ctx, **fields}, self._stream, self._clock)

    def _emit(self, level: str, message: str, **fields: Any) -> None:
        ctx = {**self._ctx, **fields}
        ts = self._clock() if self._clock is not None else None
        print(format_record(level, self.name, message, ctx, ts=ts), file=self._stream)

    def debug(self, message: str, **fields: Any) -> None:
        self._emit("DEBUG", message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        self._emit("INFO", message, **fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._emit("WARNING", message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self._emit("ERROR", message, **fields)


def get_logger(name: str, **context: Any) -> Logger:
    """Return a Logger bound to ``name`` with optional initial context (writes to stderr)."""
    return Logger(name, context)
