"""Minimal Click/Rich CLI for the C-039 walking skeleton."""
from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from core.models.job import Job
from core.walking_skeleton import DEFAULT_FIXTURE_PATH, DEFAULT_OUTPUT_PATH, run_walking_skeleton


@click.group()
def main() -> None:
    """JobHunter command-line entry point."""


@main.command()
@click.option("--profile", required=True, help="Plain-text profile for this skeleton run.")
@click.option(
    "--fixture",
    "fixture_path",
    default=str(DEFAULT_FIXTURE_PATH),
    show_default=True,
    type=click.Path(path_type=Path),
    help="JSON fixture containing raw jobs.",
)
@click.option(
    "--output",
    "output_path",
    default=str(DEFAULT_OUTPUT_PATH),
    show_default=True,
    type=click.Path(path_type=Path),
    help="JSON output file for scored results.",
)
def run(profile: str, fixture_path: Path, output_path: Path) -> None:
    """Run the walking-skeleton profile-to-results pipeline."""

    result = asyncio.run(
        run_walking_skeleton(profile, fixture_path=fixture_path, output_path=output_path)
    )
    _console().print(_results_table(result.jobs))
    click.echo(f"Exported: {result.output_path}")


def _results_table(jobs: tuple[Job, ...]) -> Table:
    table = Table(title="JobHunter Walking Skeleton")
    table.add_column("Score", justify="right")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Reason")
    for job in jobs:
        table.add_row(str(job.score or 0), job.title, job.company, job.match_reason or "")
    return table


def _console() -> Console:
    return Console(color_system=None, force_terminal=False)


if __name__ == "__main__":
    main()
