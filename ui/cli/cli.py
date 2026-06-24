"""Click/Rich CLI for JobHunter."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import click
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from core.ai_providers import BaseAIProvider
from core.ai_providers.gemini_provider import DEFAULT_GEMINI_MODEL
from core.ai_providers.openrouter_provider import DEFAULT_OPENROUTER_MODEL
from core.config import AuthConfig, Config, ConnectorSettings, OutputConfig, load_config
from core.connectors import BaseConnector
from core.models.job import Job
from core.progress import ProgressEmitter
from core.runner import build_runner, discover_plugins
from ui.cli.auth import register_cli as register_auth_cli
from ui.cli.config_cmd import register_cli

CONFIG_PATH = Path("config.yaml")


@click.group()
def main() -> None:
    """JobHunter command-line entry point."""


register_auth_cli(main)
register_cli(main)


_SMOKE_PROFILE = "Software engineer seeking a remote Python or backend role."
_SMOKE_MODEL_BY_PROVIDER = {
    "gemini": DEFAULT_GEMINI_MODEL,
    "openrouter": DEFAULT_OPENROUTER_MODEL,
}


def _load_smoke_config() -> Config:
    try:
        return load_config(CONFIG_PATH)
    except FileNotFoundError:
        return Config()
    except ValidationError as exc:
        raise click.ClickException(
            "Config file is invalid; ensure auth.* fields contain environment variable names, "
            "not credential values."
        ) from exc


def _smoke_creds_check(auth: AuthConfig, provider: str | None) -> tuple[bool, str, str | None]:
    """Return (present, reason_if_missing, resolved_provider)."""
    adzuna_id = os.environ.get(auth.adzuna_app_id_env)
    adzuna_key = os.environ.get(auth.adzuna_app_key_env)

    resolved_provider = provider
    if provider == "openrouter":
        ai_key = os.environ.get(auth.openrouter_api_key_env)
        ai_env_name = auth.openrouter_api_key_env
    elif provider == "gemini":
        ai_key = os.environ.get(auth.gemini_api_key_env)
        ai_env_name = auth.gemini_api_key_env
    else:
        ai_key = os.environ.get(auth.gemini_api_key_env)
        ai_env_name = auth.gemini_api_key_env
        if ai_key:
            resolved_provider = "gemini"
        else:
            ai_key = os.environ.get(auth.openrouter_api_key_env)
            ai_env_name = auth.openrouter_api_key_env
            if ai_key:
                resolved_provider = "openrouter"
            else:
                ai_env_name = f"{auth.gemini_api_key_env} or {auth.openrouter_api_key_env}"
                resolved_provider = None

    missing = []
    if not adzuna_id:
        missing.append(auth.adzuna_app_id_env)
    if not adzuna_key:
        missing.append(auth.adzuna_app_key_env)
    if not ai_key:
        missing.append(ai_env_name)

    if missing:
        return False, f"set {', '.join(missing)} to run live smoke", resolved_provider
    return True, "", resolved_provider


def _collect_secret_values(auth) -> list[str]:
    names = [
        auth.gemini_api_key_env,
        auth.openrouter_api_key_env,
        auth.adzuna_app_id_env,
        auth.adzuna_app_key_env,
    ]
    return [v for name in names if (v := os.environ.get(name))]


def _redact_secret_values(msg: str, auth: AuthConfig) -> str:
    for val in _collect_secret_values(auth):
        if val and val in msg:
            msg = msg.replace(val, "***")
    return msg


def _smoke_config(base_config: Config, provider: str) -> Config:
    """Return a minimal override config for smoke: 3 results, fast, Adzuna only."""
    smoke_connectors = {
        name: settings.model_copy(update={"enabled": False})
        for name, settings in base_config.connectors.items()
    }
    smoke_connectors["adzuna"] = ConnectorSettings(
        enabled=True,
        max_results=3,
        delay_min=0.0,
        delay_max=0.5,
    )
    smoke_model = (
        base_config.ai.model
        if base_config.ai.provider == provider
        else _SMOKE_MODEL_BY_PROVIDER[provider]
    )
    return base_config.model_copy(
        update={
            "ai": base_config.ai.model_copy(update={"provider": provider, "model": smoke_model}),
            "connectors": smoke_connectors,
            "output": OutputConfig(format="json", directory="output/smoke/"),
        }
    )


def _smoke_discover_factory(provider: str):
    def _smoke_discover(directory, base):
        plugins = discover_plugins(directory, base)
        if base is BaseAIProvider:
            return [plugin for plugin in plugins if getattr(plugin, "name", None) == provider]
        if base is BaseConnector:
            return [plugin for plugin in plugins if getattr(plugin, "name", None) == "adzuna"]
        return plugins

    return _smoke_discover


@main.command("smoke-validate")
@click.option(
    "--provider",
    type=click.Choice(tuple(_SMOKE_MODEL_BY_PROVIDER)),
    default=None,
    help="AI provider to use (gemini | openrouter). Auto-detected if omitted.",
)
def smoke_validate(provider: str | None) -> None:
    """Validate the live stack with a minimal real Adzuna + AI run.
    Skips cleanly when required credentials are absent.
    """
    config = _load_smoke_config()
    creds_ok, reason, resolved_provider = _smoke_creds_check(config.auth, provider)
    if not creds_ok:
        click.echo(f"Smoke skipped: {reason}.", err=True)
        return

    smoke_cfg = _smoke_config(config, resolved_provider or "gemini")

    try:
        runner = build_runner(
            smoke_cfg,
            emitter=ProgressEmitter(stream=sys.stderr),
            discover=_smoke_discover_factory(smoke_cfg.ai.provider),
        )
        result = asyncio.run(runner.run(_SMOKE_PROFILE))
    except Exception as exc:
        msg = _redact_secret_values(str(exc), config.auth)
        raise click.ClickException(f"Smoke run failed: {msg}") from exc

    n = len(result.jobs)
    top = max((j.score or 0 for j in result.jobs), default=0)
    click.echo(f"Smoke OK: {n} job(s) found, top score {top}.")


@main.command()
@click.option("--profile", default=None, help="Plain-text profile for this run.")
@click.option(
    "--profile-file",
    "profile_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Read the profile from a text file.",
)
def run(profile: str | None, profile_file: Path | None) -> None:
    """Run the full pipeline: profile -> criteria -> search -> score -> export."""
    if not profile and not profile_file:
        raise click.UsageError("Provide --profile or --profile-file.")
    source = profile_file.read_text(encoding="utf-8") if profile_file else profile
    try:
        config = load_config(CONFIG_PATH)
    except FileNotFoundError as exc:
        raise click.ClickException(f"Config file not found: {CONFIG_PATH}") from exc
    try:
        runner = build_runner(config, emitter=ProgressEmitter(stream=sys.stderr))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    result = asyncio.run(runner.run(source))
    _console().print(_results_table(result.jobs))
    for path in result.exported:
        click.echo(f"Exported: {path}")


def _results_table(jobs: tuple[Job, ...]) -> Table:
    table = Table(title="JobHunter Results")
    table.add_column("Score", justify="right")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Match")
    for job in jobs:
        table.add_row(str(job.score or 0), job.title, job.company, job.match_reason or "")
    return table


def _console() -> Console:
    return Console(color_system=None, force_terminal=False)


if __name__ == "__main__":
    main()
