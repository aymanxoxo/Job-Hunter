"""Runtime progress event emitter for CLI and desktop IPC streams."""
from __future__ import annotations

import json
import sys
from typing import Any, Literal, TextIO

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.logging import Logger, get_logger, redact

ProgressStage = Literal["profile", "criteria", "search", "score", "export"]
ProgressState = Literal["pending", "active", "done", "failed"]


class ProgressEvent(BaseModel):
    """One stdout-safe progress event for a pipeline run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["progress"] = "progress"
    run_id: str
    stage: ProgressStage
    state: ProgressState
    message: str | None = None
    current: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    metric: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_progress_bounds(self) -> ProgressEvent:
        if self.current is not None and self.total is not None and self.current > self.total:
            raise ValueError("current must be <= total")
        return self


class ProgressEmitter:
    """Imperative shell that emits progress JSON lines and matching structured logs."""

    def __init__(
        self,
        *,
        stream: TextIO | None = None,
        logger: Logger | None = None,
    ) -> None:
        self.stream = stream if stream is not None else _stdout()
        self.logger = logger if logger is not None else get_logger("core.progress")

    def emit(
        self,
        *,
        run_id: str,
        stage: ProgressStage,
        state: ProgressState,
        message: str | None = None,
        current: int | None = None,
        total: int | None = None,
        metric: dict[str, Any] | None = None,
    ) -> ProgressEvent:
        """Build, validate, emit, and return one progress event."""
        event = ProgressEvent(
            run_id=run_id,
            stage=stage,
            state=state,
            message=message,
            current=current,
            total=total,
            metric=metric,
        )
        return emit_progress_event(event, stream=self.stream, logger=self.logger)


def emit_progress_event(
    event: ProgressEvent,
    *,
    stream: TextIO | None = None,
    logger: Logger | None = None,
) -> ProgressEvent:
    """Write one progress event JSON line to stdout and log its twin to stderr."""
    destination = stream if stream is not None else _stdout()
    log = logger if logger is not None else get_logger("core.progress")
    payload = redact(event.model_dump(exclude_none=True))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=destination, flush=True)
    log.info("progress event", **_log_payload(payload))
    return event


def _log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "message" not in payload:
        return payload
    return {
        ("progress_message" if key == "message" else key): value
        for key, value in payload.items()
    }


def _stdout() -> TextIO:
    return getattr(sys, "std" + "out")
