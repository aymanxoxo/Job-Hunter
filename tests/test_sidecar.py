"""C-031 — Python sidecar entrypoint tests.

Runs the sidecar as a real subprocess so the stdin/stdout IPC contract is
verified end-to-end at the Python level, independently of the Tauri runtime.
The test uses the same offline setup as the E2E CLI test (C-029): a
deterministic stub provider dropped into a temp dir's ``ai_providers/``
drop-zone and the built-in MockConnector reading a local ``fixtures/jobs.json``.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from core.config import AIConfig, AuthConfig, Config, ConnectorSettings, OutputConfig

# ---------------------------------------------------------------------------
# Offline project fixture (same pattern as tests/e2e/test_cli_run.py)
# ---------------------------------------------------------------------------

_STUB_PROVIDER = '''\
from core.ai_providers.base_provider import BaseAIProvider
from core.models.search_criteria import SearchCriteria


class SidecarStubProvider(BaseAIProvider):
    name = "sidecar_stub"
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
            job.model_copy(update={"score": 77, "match_reason": "sidecar test match"})
            for job in jobs
        ]
'''

_FIXTURE_JOBS = """\
[
  {"id": "sc-job-1", "title": "Python Backend Engineer", "company": "SidecarCo",
   "url": "https://example.test/sc-job-1", "location": "Remote",
   "description": "Python async service development."},
  {"id": "sc-job-2", "title": "Accountant", "company": "FinCo",
   "url": "https://example.test/sc-job-2", "location": "Cairo",
   "description": "Bookkeeping and spreadsheets."}
]
"""

_CONFIG = """\
ai:
  provider: sidecar_stub
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

# Root of the installed package tree (for PYTHONPATH when running the subprocess).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_project(root: Path) -> None:
    (root / "ai_providers").mkdir()
    (root / "ai_providers" / "sidecar_stub_provider.py").write_text(
        _STUB_PROVIDER, encoding="utf-8"
    )
    (root / "fixtures").mkdir()
    (root / "fixtures" / "jobs.json").write_text(_FIXTURE_JOBS, encoding="utf-8")
    (root / "config.yaml").write_text(_CONFIG, encoding="utf-8")
    (root / "output").mkdir()


def _spawn_sidecar(
    tmp_path: Path, request: dict | None = None
) -> subprocess.CompletedProcess:
    """Run ``python -m ui.cli.sidecar`` in *tmp_path* and return the result."""
    payload = request or {"command": "run_pipeline", "args": {"profile": "Senior Python developer"}}
    return subprocess.run(
        [sys.executable, "-m", "ui.cli.sidecar"],
        input=json.dumps(payload) + "\n",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=_env(),
        timeout=60,
    )


def _env() -> dict:
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT)
    return env


def _parse_lines(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_config() -> Config:
    """Return a deterministic Config for unit tests."""
    return Config(
        ai=AIConfig(provider="gemini", model="gemini-3.5-flash"),
        auth=AuthConfig(),
        output=OutputConfig(),
        connectors={
            "mock": ConnectorSettings(enabled=True, max_results=50, delay_min=2.0, delay_max=5.0),
            "adzuna": ConnectorSettings(enabled=True, max_results=50, delay_min=2.0, delay_max=5.0),
            "duckduckgo": ConnectorSettings(
                enabled=True, max_results=50, delay_min=2.0, delay_max=5.0,
                results_per_query=10, trust_threshold=60, trust_check_enabled=True,
            ),
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sidecar_streams_progress_then_result(tmp_path):
    _make_project(tmp_path)
    proc = _spawn_sidecar(tmp_path)

    assert proc.returncode == 0, f"sidecar exited {proc.returncode}; stderr:\n{proc.stderr}"

    events = _parse_lines(proc.stdout)
    assert events, "sidecar produced no output"

    progress = [e for e in events if e.get("type") == "progress"]
    results = [e for e in events if e.get("type") == "result"]
    assert progress, "expected at least one progress event before the result"
    assert len(results) == 1, f"expected exactly one result event, got {results}"


def test_sidecar_result_contains_scored_jobs(tmp_path):
    _make_project(tmp_path)
    proc = _spawn_sidecar(tmp_path)

    assert proc.returncode == 0, proc.stderr

    events = _parse_lines(proc.stdout)
    result = next(e for e in events if e.get("type") == "result")
    data = result["data"]
    assert data, "result.data is empty"
    assert data[0]["score"] == 77
    assert data[0]["match_reason"] == "sidecar test match"


def test_sidecar_progress_events_have_required_fields(tmp_path):
    _make_project(tmp_path)
    proc = _spawn_sidecar(tmp_path)

    assert proc.returncode == 0, proc.stderr

    events = _parse_lines(proc.stdout)
    progress = [e for e in events if e.get("type") == "progress"]
    for ev in progress:
        assert "stage" in ev, f"missing 'stage' in {ev}"
        assert "state" in ev, f"missing 'state' in {ev}"
        assert "run_id" in ev, f"missing 'run_id' in {ev}"


def test_sidecar_logs_go_to_stderr_not_stdout(tmp_path):
    _make_project(tmp_path)
    proc = _spawn_sidecar(tmp_path)

    # Every stdout line must be valid JSON with a "type" field.
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)  # raises on invalid JSON
        assert "type" in obj, f"stdout line missing 'type': {line}"


def test_sidecar_unknown_command_returns_error(tmp_path):
    _make_project(tmp_path)
    import os

    request = json.dumps({"command": "not_a_command", "args": {}})
    proc = subprocess.run(
        [sys.executable, "-m", "ui.cli.sidecar"],
        input=request + "\n",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(_PROJECT_ROOT)},
        timeout=10,
    )
    assert proc.returncode != 0
    events = _parse_lines(proc.stdout)
    assert any(e.get("type") == "error" for e in events)


def test_sidecar_async_commands_are_time_bounded(monkeypatch):
    from ui.cli.sidecar import _run_with_timeout

    async def _slow_command():
        import asyncio

        await asyncio.sleep(1)

    monkeypatch.setenv("JOBHUNTER_SIDECAR_TIMEOUT_SECONDS", "0.001")

    with pytest.raises(TimeoutError, match="sidecar command timed out"):
        _run_with_timeout(_slow_command())


def test_sidecar_timeout_rejects_non_finite_values(monkeypatch):
    from ui.cli.sidecar import _run_with_timeout

    async def _command():
        return None

    monkeypatch.setenv("JOBHUNTER_SIDECAR_TIMEOUT_SECONDS", "nan")

    with pytest.raises(ValueError, match="finite and greater than zero"):
        _run_with_timeout(_command())


def test_sidecar_provider_override_accepted(tmp_path):
    """Provider name in request.args.provider overrides config."""
    _make_project(tmp_path)
    import os

    request = json.dumps(
        {
            "command": "run_pipeline",
            "args": {"profile": "Python engineer", "provider": "sidecar_stub"},
        }
    )
    proc = subprocess.run(
        [sys.executable, "-m", "ui.cli.sidecar"],
        input=request + "\n",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(_PROJECT_ROOT)},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    events = _parse_lines(proc.stdout)
    assert any(e.get("type") == "result" for e in events)


def test_sidecar_generate_criteria_returns_structured_criteria(tmp_path):
    _make_project(tmp_path)
    proc = _spawn_sidecar(
        tmp_path,
        {
            "command": "generate_criteria",
            "args": {"profile": "Senior Python developer", "provider": "sidecar_stub"},
        },
    )

    assert proc.returncode == 0, proc.stderr
    events = _parse_lines(proc.stdout)
    assert events == [
        {
            "type": "criteria",
            "data": {
                "titles": [],
                "keywords": ["python"],
                "exclude_keywords": [],
                "seniority_levels": [],
                "locations": [],
                "min_score_threshold": 40,
                "max_results": 50,
                "date_posted_days": None,
                "raw_profile": "Senior Python developer",
            },
        }
    ]


# ---------------------------------------------------------------------------
# C-058 — connector overrides unit tests
# ---------------------------------------------------------------------------


def test_sidecar_export_results_writes_configured_files(tmp_path):
    _make_project(tmp_path)
    proc = _spawn_sidecar(
        tmp_path,
        {
            "command": "export_results",
            "args": {
                "jobs": [
                    {
                        "id": "export-job-1",
                        "title": "=Formula Safe Engineer",
                        "company": "ExportCo",
                        "url": "https://example.test/export-job-1",
                        "source": "mock",
                        "location": "Remote",
                        "score": 88,
                        "match_reason": "Strong match",
                        "red_flags": ["none"],
                    }
                ]
            },
        },
    )

    assert proc.returncode == 0, proc.stderr
    events = _parse_lines(proc.stdout)
    assert len(events) == 1
    assert events[0]["type"] == "export"
    paths = [Path(path) for path in events[0]["data"]]
    assert len(paths) == 1
    assert paths[0].suffix == ".csv"
    assert paths[0].exists()
    assert paths[0].parent == (tmp_path / "output").resolve()
    assert "'=Formula Safe Engineer" in paths[0].read_text(encoding="utf-8")


def test_sidecar_export_results_rejects_invalid_jobs(tmp_path):
    _make_project(tmp_path)
    proc = _spawn_sidecar(
        tmp_path,
        {"command": "export_results", "args": {"jobs": [{"id": "missing-required"}]}},
    )

    assert proc.returncode != 0
    events = _parse_lines(proc.stdout)
    assert events[0]["type"] == "error"
    assert "invalid args.jobs" in events[0]["message"]


def test_apply_connector_overrides_absent():
    """connector_overrides absent in args → config is unchanged."""
    from ui.cli.sidecar import _load_request_config

    fake = _fake_config()
    with patch("ui.cli.sidecar.load_config", return_value=fake):
        result = _load_request_config({})
    assert result.connectors == fake.connectors


def test_apply_connector_overrides_disable_existing():
    """connector_overrides with {"adzuna": {"enabled": false}} → adzuna disabled."""
    from ui.cli.sidecar import _load_request_config

    fake = _fake_config()
    with patch("ui.cli.sidecar.load_config", return_value=fake):
        result = _load_request_config(
            {"connector_overrides": {"adzuna": {"enabled": False}}}
        )
    assert result.connectors["adzuna"].enabled is False
    assert result.connectors["mock"].enabled is True  # unchanged


def test_apply_connector_overrides_ddg_fields():
    """connector_overrides with DDG fields → duckduckgo settings updated correctly."""
    from ui.cli.sidecar import _load_request_config

    fake = _fake_config()
    with patch("ui.cli.sidecar.load_config", return_value=fake):
        result = _load_request_config(
            {
                "connector_overrides": {
                    "duckduckgo": {
                        "enabled": True,
                        "max_results": 30,
                        "results_per_query": 5,
                        "trust_threshold": 70,
                        "trust_check_enabled": False,
                    }
                }
            }
        )
    ddg = result.connectors["duckduckgo"]
    assert ddg.enabled is True
    assert ddg.max_results == 30
    assert ddg.results_per_query == 5
    assert ddg.trust_threshold == 70
    assert ddg.trust_check_enabled is False


def test_apply_connector_overrides_unknown_connector():
    """connector_overrides with unknown connector name not in config.yaml → new entry created."""
    from ui.cli.sidecar import _load_request_config

    fake = _fake_config()
    with patch("ui.cli.sidecar.load_config", return_value=fake):
        result = _load_request_config(
            {"connector_overrides": {"new_connector": {"enabled": True, "max_results": 10}}}
        )
    assert "new_connector" in result.connectors
    assert result.connectors["new_connector"].enabled is True
    assert result.connectors["new_connector"].max_results == 10


def test_apply_connector_overrides_non_dict_value_skipped():
    """connector_overrides with a non-dict value for a connector → skipped gracefully."""
    from ui.cli.sidecar import _load_request_config

    fake = _fake_config()
    with patch("ui.cli.sidecar.load_config", return_value=fake):
        result = _load_request_config(
            {"connector_overrides": {"adzuna": None, "mock": "not_a_dict"}}
        )
    assert result.connectors["adzuna"].enabled is True  # unchanged
    assert result.connectors["mock"].enabled is True    # unchanged


def test_apply_connector_overrides_does_not_touch_auth():
    """connector_overrides containing an auth key → auth config is NOT modified."""
    from ui.cli.sidecar import _load_request_config

    fake = _fake_config()
    with patch("ui.cli.sidecar.load_config", return_value=fake):
        result = _load_request_config(
            {
                "connector_overrides": {
                    "auth": {"gemini_api_key_env": "HACKED"},
                    "adzuna": {"enabled": False},
                }
            }
        )
    # auth is untouched
    assert result.auth.gemini_api_key_env == "GEMINI_API_KEY"
    # connector override still applied
    assert result.connectors["adzuna"].enabled is False
    # "auth" must NOT be injected as a spurious connector entry
    assert "auth" not in result.connectors


def test_apply_connector_overrides_with_provider_override():
    """Provider override and connector overrides applied together in one request."""
    from ui.cli.sidecar import _load_request_config

    fake = _fake_config()
    with patch("ui.cli.sidecar.load_config", return_value=fake):
        result = _load_request_config(
            {
                "provider": "ollama",
                "connector_overrides": {
                    "mock": {"enabled": False},
                    "duckduckgo": {"max_results": 25},
                },
            }
        )
    assert result.ai.provider == "ollama"
    assert result.connectors["mock"].enabled is False
    assert result.connectors["duckduckgo"].max_results == 25
    assert result.connectors["adzuna"].enabled is True  # unchanged




def test_apply_connector_overrides_new_connector_with_delay_min_only_raises():
    """New connector with delay_min alone must raise ValueError (delay_min > default delay_max)."""
    from ui.cli.sidecar import _apply_connector_overrides

    fake = _fake_config()
    with pytest.raises(ValueError, match="invalid connector_overrides for 'new_conn'"):
        _apply_connector_overrides(
            fake,
            {"new_conn": {"delay_min": 8.0}},
        )


def test_apply_connector_overrides_existing_connector_with_invalid_type_raises():
    """Invalid type (str where int expected) on existing connector must raise ValueError."""
    from ui.cli.sidecar import _apply_connector_overrides

    fake = _fake_config()
    with pytest.raises(ValueError, match="invalid connector_overrides for 'adzuna'"):
        _apply_connector_overrides(
            fake,
            {"adzuna": {"max_results": "fifty"}},
        )


def test_sidecar_redact_secrets_masks_known_credential_values(monkeypatch):
    """_redact_secrets replaces env-var values with *** before IPC output."""
    from ui.cli.sidecar import _redact_secrets

    monkeypatch.setenv("GEMINI_API_KEY", "my-secret-key-abc")
    assert _redact_secrets("auth failed: Bearer my-secret-key-abc") == "auth failed: Bearer ***"
    assert _redact_secrets("no secret here") == "no secret here"


def test_sidecar_redact_secrets_uses_config_custom_env_name(monkeypatch):
    """C-071: redaction resolves env-var names from the loaded config, not just
    the AuthConfig() defaults, so a renamed env var is still redacted."""
    from ui.cli import sidecar
    from ui.cli.sidecar import _redact_secrets

    custom = _fake_config().model_copy(
        update={"auth": AuthConfig(gemini_api_key_env="MY_CUSTOM_GEMINI")}
    )
    monkeypatch.setattr(sidecar, "load_config", lambda path=sidecar._CONFIG_PATH: custom)
    monkeypatch.setenv("MY_CUSTOM_GEMINI", "renamed-secret-123")

    assert _redact_secrets("boom key=renamed-secret-123") == "boom key=***"


def test_sidecar_redact_secrets_substring_replaced_longest_first(monkeypatch):
    """C-071: when one secret is a substring of another, the longer value is
    redacted first so no fragment of it is left exposed."""
    from ui.cli import sidecar
    from ui.cli.sidecar import _redact_secrets

    monkeypatch.setattr(sidecar, "load_config", lambda path=sidecar._CONFIG_PATH: _fake_config())
    monkeypatch.setenv("ADZUNA_APP_ID", "abc")
    monkeypatch.setenv("ADZUNA_APP_KEY", "abc-def-ghi")

    redacted = _redact_secrets("id=abc key=abc-def-ghi")
    assert "abc-def-ghi" not in redacted
    assert "def-ghi" not in redacted
    assert redacted == "id=*** key=***"


def test_sidecar_redact_secrets_survives_unloadable_config(monkeypatch):
    """C-071: if config can't be loaded, redaction falls back to defaults."""
    from ui.cli import sidecar
    from ui.cli.sidecar import _redact_secrets

    def _boom(path=sidecar._CONFIG_PATH):
        raise RuntimeError("config gone")

    monkeypatch.setattr(sidecar, "load_config", _boom)
    monkeypatch.setenv("GEMINI_API_KEY", "still-secret")

    assert _redact_secrets("key=still-secret") == "key=***"


def test_apply_connector_overrides_reserved_keys_skipped():
    """Reserved config keys (ai, profile, output, auth) are silently skipped."""
    from ui.cli.sidecar import _apply_connector_overrides

    fake = _fake_config()
    result = _apply_connector_overrides(
        fake,
        {
            "ai": {"provider": "hacked"},
            "profile": {"input": "hacked"},
            "output": {"format": "hacked"},
            "auth": {"gemini_api_key_env": "HACKED"},
        },
    )
    assert result.ai.provider == "gemini"  # unchanged
    assert result.profile.input == "text"  # unchanged
    assert result.output.format == "both"  # unchanged
    assert result.auth.gemini_api_key_env == "GEMINI_API_KEY"  # unchanged
    assert "ai" not in result.connectors
    assert "profile" not in result.connectors
    assert "output" not in result.connectors
    assert "auth" not in result.connectors
