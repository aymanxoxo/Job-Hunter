"""Tauri desktop sidecar entrypoint (SDD §11.1).

Reads one ``run_pipeline`` JSON request from stdin, runs the pipeline with
progress events emitted to STDOUT (the IPC channel), then writes the final
``{"type": "result", ...}`` line.  All Python logs go to STDERR so they never
corrupt the JSON stream.

Usage (from the project root, with CWD = project root or a dir that has
config.yaml + user drop-zone folders):

    python -m ui.cli.sidecar

Request format (one JSON line on stdin):
    {"command": "run_pipeline", "args": {"profile": "...", "provider": "ollama"}}

Response (newline-delimited JSON on stdout):
    {"type": "progress", "stage": "...", "state": "...", ...}  # zero or more
    {"type": "result", "data": [{...job fields...}]}           # final line
    {"type": "error",  "message": "..."}                       # on fatal error
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from core.config import load_config
from core.logging import get_logger
from core.models.job import Job
from core.progress import ProgressEmitter
from core.runner import build_runner

_CONFIG_PATH = Path("config.yaml")
_log = get_logger("ui.sidecar")


def _job_to_dict(job: Job) -> dict:
    return job.model_dump(mode="json")


def _error(message: str) -> None:
    print(json.dumps({"type": "error", "message": message}), file=sys.stdout, flush=True)


def main() -> None:
    raw = sys.stdin.readline()
    if not raw:
        _error("empty request")
        sys.exit(1)

    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        _error(f"invalid JSON request: {exc}")
        sys.exit(1)

    command = request.get("command")
    if command != "run_pipeline":
        _error(f"unknown command: {command!r}")
        sys.exit(1)

    args = request.get("args") or {}
    profile = args.get("profile", "")
    if not profile:
        _error("args.profile is required")
        sys.exit(1)

    try:
        config = load_config(_CONFIG_PATH)
    except Exception as exc:
        _error(f"config load failed: {exc}")
        sys.exit(1)

    # Allow provider override from request args (useful in tests and UI "Settings").
    provider_override = args.get("provider")
    if provider_override:
        config = config.model_copy(
            update={"ai": config.ai.model_copy(update={"provider": provider_override})}
        )

    try:
        # Progress events go to stdout (the IPC channel); logs stay on stderr.
        runner = build_runner(config, emitter=ProgressEmitter(stream=sys.stdout))
    except ValueError as exc:
        _error(str(exc))
        sys.exit(1)

    try:
        result = asyncio.run(runner.run(profile))
    except Exception as exc:
        _log.error("pipeline failed", error=str(exc))
        _error(f"pipeline failed: {exc}")
        sys.exit(1)

    data = [_job_to_dict(j) for j in result.jobs]
    print(json.dumps({"type": "result", "data": data}), file=sys.stdout, flush=True)


if __name__ == "__main__":
    main()
