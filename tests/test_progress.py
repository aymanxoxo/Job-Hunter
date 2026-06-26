"""C-023 - runtime progress event emitter."""
from __future__ import annotations

import io
import json

import pytest
from pydantic import ValidationError

from core.logging import Logger
from core.progress import ProgressEmitter, ProgressEvent, emit_progress_event


class FlushTrackingStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def _logger() -> tuple[Logger, io.StringIO]:
    stream = io.StringIO()
    return Logger("test.progress", stream=stream, clock=lambda: "T"), stream


def test_progress_event_schema_matches_runtime_contract():
    event = ProgressEvent(
        run_id="run-1",
        stage="search",
        state="active",
        connector="adzuna",
        message="Searching Adzuna",
        current=3,
        total=6,
        metric={"jobs": 47},
    )

    assert event.model_dump(exclude_none=True) == {
        "type": "progress",
        "run_id": "run-1",
        "stage": "search",
        "state": "active",
        "connector": "adzuna",
        "message": "Searching Adzuna",
        "current": 3,
        "total": 6,
        "metric": {"jobs": 47},
    }


def test_emit_progress_event_writes_json_line_to_stdout_stream_and_logs_twin():
    stdout = io.StringIO()
    logger, stderr = _logger()
    event = ProgressEvent(run_id="run-1", stage="search", state="done", metric={"jobs": 12})

    returned = emit_progress_event(event, stream=stdout, logger=logger)

    assert returned is event
    assert json.loads(stdout.getvalue()) == {
        "metric": {"jobs": 12},
        "run_id": "run-1",
        "stage": "search",
        "state": "done",
        "type": "progress",
    }
    log_record = json.loads(stderr.getvalue())
    assert log_record["level"] == "INFO"
    assert log_record["msg"] == "progress event"
    assert log_record["run_id"] == "run-1"
    assert log_record["stage"] == "search"
    assert log_record["state"] == "done"


def test_progress_emitter_convenience_builds_event_and_flushes_stream():
    stdout = FlushTrackingStream()
    logger, _stderr = _logger()
    emitter = ProgressEmitter(stream=stdout, logger=logger)

    event = emitter.emit(
        run_id="run-1",
        stage="export",
        state="active",
        message="Writing files",
    )

    assert event.stage == "export"
    assert stdout.getvalue().endswith("\n")
    assert stdout.flush_count == 1


def test_progress_emitter_uses_stdout_for_protocol_and_stderr_for_log(capsys):
    emitter = ProgressEmitter()

    emitter.emit(run_id="run-1", stage="profile", state="done")

    captured = capsys.readouterr()
    assert json.loads(captured.out)["type"] == "progress"
    assert json.loads(captured.err)["msg"] == "progress event"


@pytest.mark.parametrize("stage", ["login", "scoring"])
def test_progress_event_rejects_unknown_stage(stage: str):
    with pytest.raises(ValidationError):
        ProgressEvent(run_id="run-1", stage=stage, state="active")


@pytest.mark.parametrize("state", ["started", "complete"])
def test_progress_event_rejects_unknown_state(state: str):
    with pytest.raises(ValidationError):
        ProgressEvent(run_id="run-1", stage="score", state=state)


def test_progress_event_accepts_search_connector_sub_row():
    event = ProgressEvent(
        run_id="run-1",
        stage="search",
        state="skipped",
        connector="mock",
        message="disabled",
        metric={"jobs": 0},
    )

    assert event.connector == "mock"
    assert event.state == "skipped"


def test_progress_event_rejects_connector_on_non_search_stage():
    with pytest.raises(ValidationError, match="connector progress"):
        ProgressEvent(run_id="run-1", stage="score", state="active", connector="mock")


def test_progress_event_rejects_current_greater_than_total():
    with pytest.raises(ValidationError, match="current"):
        ProgressEvent(run_id="run-1", stage="score", state="active", current=7, total=6)


def test_progress_payload_redacts_secret_looking_metric_keys():
    stdout = io.StringIO()
    logger, stderr = _logger()
    event = ProgressEvent(
        run_id="run-1",
        stage="search",
        state="failed",
        metric={"cookie": "secret-cookie", "jobs": 0},
    )

    emit_progress_event(event, stream=stdout, logger=logger)

    assert json.loads(stdout.getvalue())["metric"]["cookie"] == "***REDACTED***"
    assert json.loads(stderr.getvalue())["metric"]["cookie"] == "***REDACTED***"
