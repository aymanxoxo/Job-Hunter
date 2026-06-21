"""C-029 - end-to-end `jobhunter run` over fixtures producing a scored CSV.

Exercises the real CLI command top to bottom with no network and no mocks of the
pipeline: a deterministic offline provider is dropped into the project's
``ai_providers/`` drop-zone and the built-in ``MockConnector`` reads a local
``fixtures/jobs.json``. Asserts the run writes a CSV that contains scored rows.

SDD §12 (E2E: CLI) — milestone **M-03**.
"""
from __future__ import annotations

import csv
from pathlib import Path

from click.testing import CliRunner

from ui.cli.cli import main

# A self-contained, deterministic provider discovered via the cwd drop-zone.
_STUB_PROVIDER = '''\
from core.ai_providers.base_provider import BaseAIProvider
from core.models.search_criteria import SearchCriteria


class E2EStubProvider(BaseAIProvider):
    name = "e2e_stub"
    auth_methods = ("none",)
    supports_local = True

    def __init__(self, **_kw):
        pass

    async def generate_criteria(self, profile):
        return SearchCriteria(
            keywords=("python",), min_score_threshold=40, raw_profile=profile
        )

    async def score_jobs(self, jobs, criteria):
        return [
            job.model_copy(update={"score": 88, "match_reason": "strong python match"})
            for job in jobs
        ]
'''

_FIXTURE_JOBS = """\
[
  {"id": "remote-python", "title": "Senior Python Developer", "company": "Acme",
   "url": "https://example.test/jobs/remote-python", "location": "Remote",
   "description": "Build Python services with async APIs."},
  {"id": "office-data", "title": "Data Analyst", "company": "Beta",
   "url": "https://example.test/jobs/office-data", "location": "Cairo",
   "description": "Spreadsheet-heavy reporting role."}
]
"""

_CONFIG = """\
ai:
  provider: e2e_stub
  model: stub
profile:
  input: text
connectors:
  mock:
    enabled: true
    fixture_path: fixtures/jobs.json
output:
  format: csv
  directory: output/
"""


def _make_project(root: Path) -> None:
    (root / "ai_providers").mkdir()
    (root / "ai_providers" / "e2e_stub_provider.py").write_text(_STUB_PROVIDER, encoding="utf-8")
    (root / "fixtures").mkdir()
    (root / "fixtures" / "jobs.json").write_text(_FIXTURE_JOBS, encoding="utf-8")
    (root / "config.yaml").write_text(_CONFIG, encoding="utf-8")


def test_cli_run_writes_scored_csv_from_fixtures(tmp_path, monkeypatch):
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        main,
        ["run", "--profile", "Senior Python developer seeking remote work"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "Exported:" in result.output

    csv_files = list((tmp_path / "output").glob("results_*.csv"))
    assert len(csv_files) == 1, f"expected exactly one CSV export, got {csv_files}"

    rows = list(csv.DictReader(csv_files[0].read_text(encoding="utf-8").splitlines()))
    assert rows, "expected at least one scored row in the CSV"
    top = rows[0]
    assert top["title"] == "Senior Python Developer"
    assert top["company"] == "Acme"
    assert top["score"] == "88"
    assert top["match_reason"] == "strong python match"
    # The non-matching fixture job must be filtered out by keyword search.
    assert all(r["title"] != "Data Analyst" for r in rows)
