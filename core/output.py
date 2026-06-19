"""Output exporter (SDD §5.4).

Writes scored jobs to the configured ``output/`` directory as timestamped
``results_<YYYY-MM-DD_HHMMSS>.csv`` and/or ``.json`` files, per ``config.output.format``.
Pure serialization (``jobs_to_csv``/``jobs_to_json``) is separated from the file-writing shell
(``export_results``); the clock is injected so exports are deterministic in tests.
"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from core.models.job import Job

CSV_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "company",
    "url",
    "source",
    "location",
    "score",
    "match_reason",
    "red_flags",
)
_VALID_FORMATS = frozenset({"csv", "json", "both"})


def timestamp_slug(moment: datetime) -> str:
    """Render the export timestamp used in result filenames."""
    return moment.strftime("%Y-%m-%d_%H%M%S")


def jobs_to_json(jobs: Sequence[Job]) -> str:
    """Serialize jobs to a pretty, stable JSON array."""
    payload = [job.model_dump(mode="json") for job in jobs]
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def jobs_to_csv(jobs: Sequence[Job]) -> str:
    """Serialize jobs to CSV with a fixed column set; red_flags joined with '; '."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for job in jobs:
        data = job.model_dump(mode="json")
        data["red_flags"] = "; ".join(job.red_flags)
        writer.writerow({field: data.get(field, "") for field in CSV_FIELDS})
    return buffer.getvalue()


def export_results(
    jobs: Sequence[Job],
    *,
    directory: str | Path = "output/",
    fmt: str = "both",
    moment: datetime | None = None,
) -> tuple[Path, ...]:
    """Write results to ``directory`` per ``fmt`` (csv|json|both); return the files written."""
    if fmt not in _VALID_FORMATS:
        raise ValueError(f"Unknown output format: {fmt!r} (expected csv, json, or both)")
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = timestamp_slug(moment or datetime.now())
    written: list[Path] = []
    if fmt in {"csv", "both"}:
        csv_path = out_dir / f"results_{slug}.csv"
        csv_path.write_text(jobs_to_csv(jobs), encoding="utf-8")
        written.append(csv_path)
    if fmt in {"json", "both"}:
        json_path = out_dir / f"results_{slug}.json"
        json_path.write_text(jobs_to_json(jobs), encoding="utf-8")
        written.append(json_path)
    return tuple(written)
