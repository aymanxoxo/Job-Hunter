"""C-027 - CLI auth commands (SDD sections 8 and 10.1)."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from core.auth.session_store import SessionStore
from ui.cli.cli import main


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password


def _write_config(path: Path) -> None:
    path.write_text(
        """
ai:
  provider: gemini
auth:
  gemini_api_key_env: GEMINI_TEST_KEY
  openrouter_api_key_env: OPENROUTER_TEST_KEY
  adzuna_app_id_env: ADZUNA_TEST_ID
  adzuna_app_key_env: ADZUNA_TEST_KEY
""",
        encoding="utf-8",
    )


def test_auth_status_reports_api_key_and_session_state(tmp_path: Path, monkeypatch):
    _write_config(tmp_path / "config.yaml")
    session_dir = tmp_path / "sessions"
    keyring = FakeKeyring()
    SessionStore(
        root_dir=session_dir,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine",
    ).save("linkedin", {"cookies": [], "origins": []})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_TEST_KEY", "gemini-secret")
    monkeypatch.delenv("OPENROUTER_TEST_KEY", raising=False)
    runner = CliRunner()

    completed = runner.invoke(
        main,
        ["auth", "--session-dir", str(session_dir), "status"],
        obj={"keyring_backend": keyring, "machine_id_provider": lambda: "machine"},
        catch_exceptions=False,
    )

    assert completed.exit_code == 0
    assert "gemini" in completed.output
    assert "GEMINI_TEST_KEY" in completed.output
    assert "configured" in completed.output
    assert "gemini-secret" not in completed.output
    assert "openrouter" in completed.output
    assert "missing" in completed.output
    assert "linkedin" in completed.output
    assert "stored" in completed.output


def test_auth_status_shows_adzuna_ready_only_when_both_keys_are_present(
    tmp_path: Path, monkeypatch
):
    _write_config(tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ADZUNA_TEST_ID", "adzuna-id-secret")
    monkeypatch.delenv("ADZUNA_TEST_KEY", raising=False)
    runner = CliRunner()

    missing = runner.invoke(main, ["auth", "status"], catch_exceptions=False)
    monkeypatch.setenv("ADZUNA_TEST_KEY", "adzuna-key-secret")
    configured = runner.invoke(main, ["auth", "status"], catch_exceptions=False)

    assert missing.exit_code == 0
    assert "adzuna" in missing.output
    assert "missing" in missing.output
    assert configured.exit_code == 0
    assert "configured" in configured.output
    assert "adzuna-id-secret" not in configured.output
    assert "adzuna-key-secret" not in configured.output


def test_auth_logout_deletes_stored_session(tmp_path: Path, monkeypatch):
    _write_config(tmp_path / "config.yaml")
    session_dir = tmp_path / "sessions"
    keyring = FakeKeyring()
    store = SessionStore(
        root_dir=session_dir,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine",
    )
    store.save("linkedin", {"cookies": [], "origins": []})
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(
        main,
        ["auth", "--session-dir", str(session_dir), "logout", "linkedin"],
        obj={"keyring_backend": keyring, "machine_id_provider": lambda: "machine"},
        catch_exceptions=False,
    )

    assert completed.exit_code == 0
    assert "Logged out: linkedin" in completed.output
    assert store.exists("linkedin") is False


def test_auth_logout_rejects_api_key_services(tmp_path: Path, monkeypatch):
    _write_config(tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(main, ["auth", "logout", "gemini"])

    assert completed.exit_code != 0
    assert "unset GEMINI_TEST_KEY" in completed.output


def test_deferred_auth_flows_return_clear_errors(tmp_path: Path, monkeypatch):
    _write_config(tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    google = runner.invoke(main, ["auth", "google"])
    linkedin = runner.invoke(main, ["auth", "linkedin"])

    assert google.exit_code != 0
    assert "deferred to C-016" in google.output
    assert linkedin.exit_code != 0
    assert "deferred" in linkedin.output
