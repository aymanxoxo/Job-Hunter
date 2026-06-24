"""Tauri desktop sidecar entrypoint (SDD §11.1).

Reads one JSON request from stdin. ``run_pipeline`` runs the pipeline with
progress events emitted to STDOUT (the IPC channel), then writes the final
``{"type": "result", ...}`` line. ``generate_criteria`` invokes the configured
provider's criteria generation and writes a ``{"type": "criteria", ...}``
line. All Python logs go to STDERR so they never corrupt the JSON stream.

Usage (from the project root, with CWD = project root or a dir that has
config.yaml + user drop-zone folders):

    python -m ui.cli.sidecar

Request format (one JSON line on stdin):
    {"command": "run_pipeline", "args": {"profile": "...", "provider": "ollama"}}
    {"command": "generate_criteria", "args": {"profile": "...", "provider": "ollama"}}

Response (newline-delimited JSON on stdout):
    {"type": "progress", "stage": "...", "state": "...", ...}  # zero or more
    {"type": "result", "data": [{...job fields...}]}           # final line
    {"type": "criteria", "data": {...SearchCriteria fields...}} # criteria generation
    {"type": "error",  "message": "..."}                       # on fatal error
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from core.config import Config, ConnectorSettings, load_config
from core.logging import get_logger
from core.models.job import Job
from core.progress import ProgressEmitter
from core.runner import build_runner

_CONFIG_PATH = Path("config.yaml")
_log = get_logger("ui.sidecar")

_RESERVED_CONFIG_KEYS = frozenset({"ai", "profile", "connectors", "output", "auth"})


def _job_to_dict(job: Job) -> dict:
    return job.model_dump(mode="json")


def _write_event(event: dict) -> None:
    print(json.dumps(event), file=sys.stdout, flush=True)


def _error(message: str) -> None:
    _write_event({"type": "error", "message": message})


def _profile_arg(args: dict) -> str:
    profile = args.get("profile", "")
    if not profile:
        raise ValueError("args.profile is required")
    return profile


def _apply_connector_overrides(config, overrides: dict) -> Config:
    """Merge connector_overrides from the IPC request into the loaded config.
    Only updates fields that are present in the override dict; never touches auth.
    Raises ValueError for invalid overrides (including Pydantic validation errors).
    """
    connector_map = dict(config.connectors)
    for name, fields in overrides.items():
        if not isinstance(fields, dict):
            continue
        if name in _RESERVED_CONFIG_KEYS:
            continue
        existing = connector_map.get(name)
        if existing is not None:
            # merge into existing ConnectorSettings — re-validate to run constraints
            filtered = {
                k: v for k, v in fields.items()
                if k in existing.__class__.model_fields
            }
            try:
                updated = existing.__class__.model_validate({
                    **existing.model_dump(),
                    **filtered,
                })
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"invalid connector_overrides for '{name}': {exc}") from exc
        else:
            # new connector not in config.yaml — create from scratch
            filtered = {
                k: v for k, v in fields.items()
                if k in ConnectorSettings.model_fields
            }
            try:
                updated = ConnectorSettings(**filtered)
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"invalid connector_overrides for '{name}': {exc}") from exc
        connector_map[name] = updated
    return config.model_copy(update={"connectors": connector_map})


def _load_request_config(args: dict):
    try:
        config = load_config(_CONFIG_PATH)
    except Exception as exc:
        raise ValueError(f"config load failed: {exc}") from exc

    provider_override = args.get("provider")
    if provider_override:
        config = config.model_copy(
            update={"ai": config.ai.model_copy(update={"provider": provider_override})}
        )

    connector_overrides = args.get("connector_overrides")
    if isinstance(connector_overrides, dict):
        try:
            config = _apply_connector_overrides(config, connector_overrides)
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"invalid connector_overrides: {exc}") from exc

    return config


async def _generate_criteria(profile: str, args: dict) -> None:
    config = _load_request_config(args)
    try:
        runner = build_runner(config)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    profile_text = await runner.profile_input.to_text(profile)
    criteria = await runner.provider.generate_criteria(profile_text)
    _write_event({"type": "criteria", "data": criteria.model_dump(mode="json")})


async def _run_pipeline(profile: str, args: dict) -> None:
    config = _load_request_config(args)

    try:
        # Progress events go to stdout (the IPC channel); logs stay on stderr.
        runner = build_runner(config, emitter=ProgressEmitter(stream=sys.stdout))
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    result = await runner.run(profile)
    data = [_job_to_dict(j) for j in result.jobs]
    _write_event({"type": "result", "data": data})


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

    args = request.get("args") or {}
    command = request.get("command")
    try:
        profile = _profile_arg(args)
    except ValueError as exc:
        _error(str(exc))
        sys.exit(1)

    try:
        if command == "run_pipeline":
            asyncio.run(_run_pipeline(profile, args))
        elif command == "generate_criteria":
            asyncio.run(_generate_criteria(profile, args))
        else:
            _error(f"unknown command: {command!r}")
            sys.exit(1)
    except Exception as exc:
        _log.error("sidecar command failed", command=command, error=str(exc))
        _error(f"{command or 'command'} failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
