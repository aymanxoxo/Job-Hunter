"""E2E tests for the smoke-validate CLI command (C-059)."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import ui.cli.cli as cli_module
from core.ai_providers import BaseAIProvider
from core.ai_providers.openrouter_provider import DEFAULT_OPENROUTER_MODEL
from core.connectors import BaseConnector
from ui.cli.cli import main

_LIVE = (
    os.environ.get("ADZUNA_APP_ID")
    and os.environ.get("ADZUNA_APP_KEY")
    and (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENROUTER_API_KEY"))
)
class TestSmokeValidateSkip:
    """Tests that exercise the skip path — no credentials required."""

    @pytest.fixture(autouse=True)
    def _clear_creds(self, monkeypatch):
        """Remove all credential env vars before each test."""
        for name in (
            "ADZUNA_APP_ID",
            "ADZUNA_APP_KEY",
            "GEMINI_API_KEY",
            "OPENROUTER_API_KEY",
        ):
            monkeypatch.delenv(name, raising=False)

    def test_skip_when_no_creds_set(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["smoke-validate"])
        assert result.exit_code == 0
        assert "Smoke skipped" in result.output
        assert "ADZUNA_APP_ID" in result.output
        assert "ADZUNA_APP_KEY" in result.output
        assert "GEMINI_API_KEY" in result.output or "OPENROUTER_API_KEY" in result.output

    def test_skip_when_only_adzuna_creds_no_ai(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ADZUNA_APP_ID", "fake_id")
        monkeypatch.setenv("ADZUNA_APP_KEY", "fake_key")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["smoke-validate"])
        assert result.exit_code == 0
        assert "Smoke skipped" in result.output
        assert "GEMINI_API_KEY" in result.output or "OPENROUTER_API_KEY" in result.output

    def test_skip_when_only_ai_creds_no_adzuna(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["smoke-validate"])
        assert result.exit_code == 0
        assert "Smoke skipped" in result.output
        assert "ADZUNA_APP_ID" in result.output
        assert "ADZUNA_APP_KEY" in result.output

    def test_skip_provider_openrouter_checks_right_var(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ADZUNA_APP_ID", "fake_id")
        monkeypatch.setenv("ADZUNA_APP_KEY", "fake_key")
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["smoke-validate", "--provider", "openrouter"])
        assert result.exit_code == 0
        assert "Smoke skipped" in result.output
        assert "OPENROUTER_API_KEY" in result.output
        assert "GEMINI_API_KEY" not in result.output

    def test_skip_provider_gemini_checks_right_var(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ADZUNA_APP_ID", "fake_id")
        monkeypatch.setenv("ADZUNA_APP_KEY", "fake_key")
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["smoke-validate", "--provider", "gemini"])
        assert result.exit_code == 0
        assert "Smoke skipped" in result.output
        assert "GEMINI_API_KEY" in result.output
        assert "OPENROUTER_API_KEY" not in result.output

    def test_secret_redaction_guard(self, monkeypatch, tmp_path):
        """Credential values that leak into exception messages are redacted."""
        secret = "abc123secret"
        monkeypatch.setenv("ADZUNA_APP_ID", "fake_id")
        monkeypatch.setenv("ADZUNA_APP_KEY", "fake_key")
        monkeypatch.setenv("GEMINI_API_KEY", secret)
        monkeypatch.chdir(tmp_path)

        def _boom(*args, **kwargs):
            raise RuntimeError(f"key={secret}")

        monkeypatch.setattr("ui.cli.cli.build_runner", _boom)

        result = CliRunner().invoke(main, ["smoke-validate"])
        assert result.exit_code != 0
        assert "Smoke run failed" in result.output
        assert secret not in result.output
        assert "***" in result.output

    def test_rejects_unknown_provider(self):
        result = CliRunner().invoke(main, ["smoke-validate", "--provider", "bogus"])
        assert result.exit_code != 0
        assert "Invalid value for '--provider'" in result.output

    def test_invalid_config_does_not_print_secret_like_value(self, monkeypatch, tmp_path):
        secret = "abc123secret"
        (tmp_path / "config.yaml").write_text(
            f"auth:\n  gemini_api_key_env: {secret}\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main, ["smoke-validate"])

        assert result.exit_code != 0
        assert "Config file is invalid" in result.output
        assert secret not in result.output

    def test_openrouter_smoke_uses_openrouter_default_model(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ADZUNA_APP_ID", "fake_id")
        monkeypatch.setenv("ADZUNA_APP_KEY", "fake_key")
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")
        monkeypatch.chdir(tmp_path)
        captured = {}

        class _Runner:
            async def run(self, profile):
                return SimpleNamespace(jobs=())

        def _build_runner(config, **kwargs):
            captured["config"] = config
            return _Runner()

        monkeypatch.setattr("ui.cli.cli.build_runner", _build_runner)

        result = CliRunner().invoke(main, ["smoke-validate", "--provider", "openrouter"])

        assert result.exit_code == 0, result.output
        assert captured["config"].ai.provider == "openrouter"
        assert captured["config"].ai.model == DEFAULT_OPENROUTER_MODEL

    def test_smoke_discovery_allows_only_selected_provider_and_adzuna(self, monkeypatch):
        class GeminiProvider(BaseAIProvider):
            name = "gemini"

        class OpenRouterProvider(BaseAIProvider):
            name = "openrouter"

        class AdzunaConnector(BaseConnector):
            name = "adzuna"

        class OtherConnector(BaseConnector):
            name = "duckduckgo"

        def _discover(_directory, base):
            if base is BaseAIProvider:
                return [GeminiProvider, OpenRouterProvider]
            if base is BaseConnector:
                return [AdzunaConnector, OtherConnector]
            return []

        monkeypatch.setattr(cli_module, "discover_plugins", _discover)
        discover = cli_module._smoke_discover_factory("openrouter")

        assert discover("ai_providers", BaseAIProvider) == [OpenRouterProvider]
        assert discover("connectors", BaseConnector) == [AdzunaConnector]


@pytest.mark.skipif(not _LIVE, reason="real credentials required")
def test_smoke_validate_live_run_succeeds():
    result = CliRunner().invoke(main, ["smoke-validate"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Smoke OK:" in result.output
