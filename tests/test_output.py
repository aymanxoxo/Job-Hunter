"""C-024 - output exporter (SDD §5.4): timestamped CSV/JSON to output/."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

import pytest

from core.models.job import Job
from core.output import export_results, jobs_to_csv, jobs_to_json, timestamp_slug


def _job(**over) -> Job:
    base = dict(id="1", title="Dev", company="Acme", url="https://x", source="mock")
    base.update(over)
    return Job(**base)


def test_timestamp_slug_format():
    assert timestamp_slug(datetime(2026, 6, 19, 14, 5, 9)) == "2026-06-19_140509"


def test_jobs_to_json_includes_fields():
    data = json.loads(jobs_to_json([_job(score=80, red_flags=("x",))]))
    assert data[0]["id"] == "1"
    assert data[0]["score"] == 80
    assert data[0]["red_flags"] == ["x"]


def test_jobs_to_csv_header_and_joined_red_flags():
    text = jobs_to_csv([_job(score=80, red_flags=("a", "b"))])
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][:3] == ["id", "title", "company"]
    assert "a; b" in text
    assert "80" in text


def test_export_both_writes_two_timestamped_files(tmp_path):
    written = export_results(
        [_job(score=90)], directory=tmp_path, fmt="both", moment=datetime(2026, 6, 19, 14, 5, 9)
    )
    names = sorted(path.name for path in written)
    assert names == ["results_2026-06-19_140509.csv", "results_2026-06-19_140509.json"]
    assert all(path.exists() for path in written)


def test_export_csv_only_empty_jobs_is_header(tmp_path):
    written = export_results(
        [], directory=tmp_path, fmt="csv", moment=datetime(2026, 6, 19, 1, 2, 3)
    )
    assert [path.suffix for path in written] == [".csv"]
    assert written[0].read_text(encoding="utf-8").strip().startswith("id,title,company")


def test_export_json_only(tmp_path):
    written = export_results(
        [_job()], directory=tmp_path, fmt="json", moment=datetime(2026, 1, 1, 0, 0, 0)
    )
    assert [path.suffix for path in written] == [".json"]


def test_export_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        export_results([], directory=tmp_path, fmt="xml")


def test_jobs_to_csv_escapes_formula_injection():
    job = _job(
        title="=cmd|'/c calc'!A1",
        company="@SUM(1+1)",
        match_reason="-2+3",
        red_flags=("+danger", "ok"),
    )
    text = jobs_to_csv([job])
    rows = list(csv.reader(io.StringIO(text)))
    row = rows[1]
    by_field = dict(zip(rows[0], row, strict=True))

    assert by_field["title"] == "'=cmd|'/c calc'!A1"
    assert by_field["company"] == "'@SUM(1+1)"
    assert by_field["match_reason"] == "'-2+3"
    assert by_field["red_flags"] == "'+danger; ok"


def test_jobs_to_csv_leaves_benign_cells_untouched():
    text = jobs_to_csv([_job(title="Senior Dev", company="Acme", score=80)])
    header, row = list(csv.reader(io.StringIO(text)))
    by_field = dict(zip(header, row, strict=True))

    assert by_field["title"] == "Senior Dev"
    assert by_field["company"] == "Acme"
    assert by_field["score"] == "80"
