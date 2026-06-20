"""Click/Rich CLI for JobHunter."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from core.config import load_config
from core.models.job import Job
from core.progress import ProgressEmitter
from core.runner import build_runner
from ui.cli.config_cmd import register_cli

CONFIG_PATH = Path("config.yaml")


@click.group()
def main() -> None:
    """JobHunter command-line entry point."""


register_cli(main)


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
