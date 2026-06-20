"""Config, plugin listing, and result export CLI commands (C-028)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import click
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

import core.ai_providers as ai_provider_pkg
import core.connectors as connector_pkg
from core.ai_providers import BaseAIProvider
from core.config import Config, load_config
from core.connectors import BaseConnector
from core.models.job import Job
from core.output import export_results
from core.runner import discover_plugins

CONFIG_PATH = Path("config.yaml")


@click.group(name="config")
def config_group() -> None:
    """Inspect JobHunter configuration."""


@config_group.command(name="show")
def config_show() -> None:
    """Print resolved config with auth values redacted."""
    config = _load_config()
    click.echo(yaml.safe_dump(_redacted_config(config), sort_keys=False))


@click.group(name="connectors")
def connectors_group() -> None:
    """Inspect connector plugins."""


@connectors_group.command(name="list")
def connectors_list() -> None:
    """Show all loaded connectors and config status."""
    config = _load_config()
    rows = _discover_rows(
        BaseConnector,
        built_in_dir=Path(connector_pkg.__file__).resolve().parent,
        drop_zone=Path("connectors"),
    )
    table = Table(title="Connectors")
    table.add_column("Name")
    table.add_column("Class")
    table.add_column("Source")
    table.add_column("Auth")
    table.add_column("Status")
    for row in rows:
        setting = config.connectors.get(row.name)
        enabled = (
            setting.enabled if setting is not None else bool(getattr(row.plugin, "enabled", True))
        )
        table.add_row(
            row.name,
            row.plugin.__name__,
            row.source,
            ", ".join(getattr(row.plugin, "auth_methods", ())) or "-",
            "enabled" if enabled else "disabled",
        )
    _console().print(table)


@click.group(name="providers")
def providers_group() -> None:
    """Inspect AI provider plugins."""


@providers_group.command(name="list")
def providers_list() -> None:
    """Show all loaded AI providers."""
    rows = _discover_rows(
        BaseAIProvider,
        built_in_dir=Path(ai_provider_pkg.__file__).resolve().parent,
        drop_zone=Path("ai_providers"),
    )
    table = Table(title="AI Providers")
    table.add_column("Name")
    table.add_column("Class")
    table.add_column("Source")
    table.add_column("Auth")
    table.add_column("Local")
    for row in rows:
        table.add_row(
            row.name,
            row.plugin.__name__,
            row.source,
            ", ".join(getattr(row.plugin, "auth_methods", ())) or "-",
            "yes" if getattr(row.plugin, "supports_local", False) else "no",
        )
    _console().print(table)


@click.command(name="export")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["csv", "json", "both"]),
    default=None,
    help="Output format to write. Defaults to config.output.format.",
)
def export_cmd(fmt: str | None) -> None:
    """Re-export the newest JSON results file in the configured output directory."""
    config = _load_config()
    output_dir = Path(config.output.directory)
    source = _latest_results_json(output_dir)
    jobs = _load_jobs(source)
    written = export_results(jobs, directory=output_dir, fmt=fmt or config.output.format)
    for path in written:
        click.echo(f"Exported: {path}")


def register_cli(main: click.Group) -> None:
    """Attach C-028 command groups to the root CLI."""
    main.add_command(config_group)
    main.add_command(connectors_group)
    main.add_command(providers_group)
    main.add_command(export_cmd)


@dataclass(frozen=True)
class PluginRow:
    plugin: type
    source: str

    @property
    def name(self) -> str:
        return str(getattr(self.plugin, "name", self.plugin.__name__))


def _load_config(path: Path = CONFIG_PATH) -> Config:
    try:
        return load_config(path)
    except FileNotFoundError as exc:
        raise click.ClickException(f"Config file not found: {path}") from exc
    except ValidationError as exc:
        raise click.ClickException(f"Config is invalid: {exc}") from exc


def _redacted_config(config: Config) -> dict:
    data = config.model_dump(mode="json")
    data["auth"] = {key: "<redacted>" for key in data.get("auth", {})}
    return data


def _discover_rows(base_class: type, *, built_in_dir: Path, drop_zone: Path) -> list[PluginRow]:
    rows: list[PluginRow] = []
    seen: set[tuple[str, str]] = set()
    for source, directory in (("built-in", built_in_dir), ("user", drop_zone)):
        for plugin in discover_plugins(directory, base_class):
            identity = (plugin.__module__, plugin.__name__)
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(PluginRow(plugin=plugin, source=source))
    return sorted(rows, key=lambda row: (row.name, row.plugin.__name__, row.source))


def _latest_results_json(output_dir: Path) -> Path:
    candidates = sorted(output_dir.glob("results_*.json"), key=lambda path: path.name)
    if not candidates:
        raise click.ClickException(f"No prior JSON results found in {output_dir}")
    return candidates[-1]


def _load_jobs(path: Path) -> list[Job]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Last results file is not valid JSON: {path}") from exc
    records = payload.get("jobs") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise click.ClickException(f"Last results file must contain a JSON list of jobs: {path}")
    try:
        return [Job.model_validate(record) for record in records]
    except ValidationError as exc:
        message = f"Last results file contains invalid jobs: {path}: {exc}"
        raise click.ClickException(message) from exc


def _console() -> Console:
    return Console(color_system=None, force_terminal=False)
