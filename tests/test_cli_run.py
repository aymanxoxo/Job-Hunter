"""C-026 - real `jobhunter run` command wiring the Runner (SDD §10)."""
from __future__ import annotations

import io
from datetime import datetime
from unittest.mock import MagicMock

from click.testing import CliRunner

import ui.cli.cli as cli_module
from core.ai_providers import BaseAIProvider
from core.config import AuthConfig
from core.connectors import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from core.progress import ProgressEmitter
from core.runner import Runner
from ui.cli.cli import main


class _StubProvider(BaseAIProvider):
    name = "stub"
    auth_methods = ("none",)

    async def generate_criteria(self, profile):
        return SearchCriteria(raw_profile=profile, min_score_threshold=0)

    async def score_jobs(self, jobs, criteria):
        return [job.model_copy(update={"score": 80, "match_reason": "good fit"}) for job in jobs]


class _FakeConnector(BaseConnector):
    name = "fake"
    auth_methods = ("none",)

    async def search(self, criteria):
        return [Job(id="1", title="Senior Dev", company="Acme", url="https://x/1", source="fake")]


def test_run_executes_pipeline_and_renders_table(tmp_path, monkeypatch):
    def fake_build_runner(config, **kwargs):
        return Runner(
            provider=_StubProvider(),
            connectors=[_FakeConnector()],
            output_dir=tmp_path,
            output_format="json",
            emitter=ProgressEmitter(stream=io.StringIO()),
            clock=lambda: datetime(2026, 6, 20, 1, 2, 3),
            run_id="rid",
        )

    monkeypatch.setattr(cli_module, "load_config", lambda path=cli_module.CONFIG_PATH: object())
    monkeypatch.setattr(cli_module, "build_runner", fake_build_runner)

    completed = CliRunner().invoke(main, ["run", "--profile", "python dev"], catch_exceptions=False)

    assert completed.exit_code == 0, completed.output
    assert "Senior Dev" in completed.output
    assert "Acme" in completed.output
    assert "good fit" in completed.output
    assert "Exported:" in completed.output


def test_run_requires_a_profile_source():
    completed = CliRunner().invoke(main, ["run"])
    assert completed.exit_code != 0
    assert "Provide --profile" in completed.output


def test_run_redacts_secret_from_pipeline_exception(monkeypatch):
    """Exceptions from runner.run() must be caught and credential values redacted."""
    secret = "test-gemini-key-xyz"
    monkeypatch.setenv("GEMINI_API_KEY", secret)

    fake_config = MagicMock()
    fake_config.auth = AuthConfig()

    async def failing_run(profile):
        raise RuntimeError(f"HTTP 401: key={secret}")

    fake_runner = MagicMock()
    fake_runner.run = failing_run

    monkeypatch.setattr(cli_module, "load_config", lambda path=cli_module.CONFIG_PATH: fake_config)
    monkeypatch.setattr(cli_module, "build_runner", lambda config, **kwargs: fake_runner)

    completed = CliRunner().invoke(main, ["run", "--profile", "python dev"])

    assert completed.exit_code != 0
    assert secret not in completed.output
    assert "***" in completed.output
