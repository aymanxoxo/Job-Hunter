"""C-028 - CLI config/list/export commands (SDD section 10.1)."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from core.models.job import Job
from core.output import jobs_to_json
from ui.cli.cli import main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _config(path: Path, output_dir: str = "output") -> None:
    _write(
        path / "config.yaml",
        f"""
ai:
  provider: ollama
connectors:
  mock:
    enabled: true
  drop:
    enabled: false
output:
  directory: {output_dir}
auth:
  gemini_api_key_env: SECRET_ENV_NAME
""",
    )


def test_config_show_prints_resolved_config_with_auth_redacted(tmp_path: Path, monkeypatch):
    _config(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(main, ["config", "show"], catch_exceptions=False, obj={})

    assert completed.exit_code == 0
    assert "provider: ollama" in completed.output
    assert "gemini_api_key_env: <redacted>" in completed.output
    assert "SECRET_ENV_NAME" not in completed.output


def test_connectors_list_includes_builtin_and_user_drop_zone(tmp_path: Path, monkeypatch):
    _config(tmp_path)
    _write(
        tmp_path / "connectors" / "drop_connector.py",
        """
from core.connectors import BaseConnector

class DropConnector(BaseConnector):
    name = "drop"
    auth_methods = ("session",)

    async def search(self, criteria):
        return []
""",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(main, ["connectors", "list"], catch_exceptions=False)

    assert completed.exit_code == 0
    assert "mock" in completed.output
    assert "MockConnector" in completed.output
    assert "drop" in completed.output
    assert "DropConnector" in completed.output
    assert "disabled" in completed.output


def test_providers_list_includes_builtin_and_user_drop_zone(tmp_path: Path, monkeypatch):
    _config(tmp_path)
    _write(
        tmp_path / "ai_providers" / "drop_provider.py",
        """
from core.ai_providers import BaseAIProvider
from core.models.search_criteria import SearchCriteria

class DropProvider(BaseAIProvider):
    name = "drop-ai"
    auth_methods = ("api_key",)

    async def generate_criteria(self, profile):
        return SearchCriteria(raw_profile=profile)

    async def score_jobs(self, jobs, criteria):
        return jobs
""",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(main, ["providers", "list"], catch_exceptions=False)

    assert completed.exit_code == 0
    assert "ollama" in completed.output
    assert "OllamaProvider" in completed.output
    assert "drop-ai" in completed.output
    assert "DropProvider" in completed.output


def test_list_commands_tolerate_empty_drop_zones(tmp_path: Path, monkeypatch):
    _config(tmp_path)
    (tmp_path / "connectors").mkdir()
    (tmp_path / "ai_providers").mkdir()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    connectors = runner.invoke(main, ["connectors", "list"], catch_exceptions=False)
    providers = runner.invoke(main, ["providers", "list"], catch_exceptions=False)

    assert connectors.exit_code == 0
    assert providers.exit_code == 0
    assert "mock" in connectors.output
    assert "ollama" in providers.output


def test_export_rewrites_newest_json_results_in_requested_format(tmp_path: Path, monkeypatch):
    _config(tmp_path, output_dir="out")
    out = tmp_path / "out"
    out.mkdir()
    older = Job(id="old", title="Old", company="Acme", url="https://old", source="mock")
    newest = Job(id="new", title="New", company="Acme", url="https://new", source="mock")
    _write(out / "results_2026-01-01_010101.json", jobs_to_json([older]))
    _write(out / "results_2026-01-02_010101.json", jobs_to_json([newest]))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(main, ["export", "--format", "csv"], catch_exceptions=False)

    assert completed.exit_code == 0
    exported = sorted(out.glob("results_*.csv"))
    assert len(exported) == 1
    assert "new" in exported[0].read_text(encoding="utf-8")
    assert "old" not in exported[0].read_text(encoding="utf-8")
    assert exported[0].name in completed.output


def test_export_reports_clean_error_when_no_prior_json_results(tmp_path: Path, monkeypatch):
    _config(tmp_path, output_dir="out")
    (tmp_path / "out").mkdir()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(main, ["export", "--format", "csv"])

    assert completed.exit_code != 0
    assert "No prior JSON results found" in completed.output


def test_export_rejects_invalid_format(tmp_path: Path, monkeypatch):
    _config(tmp_path, output_dir="out")
    (tmp_path / "out").mkdir()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(main, ["export", "--format", "xml"])

    assert completed.exit_code != 0
    assert "Invalid value" in completed.output
