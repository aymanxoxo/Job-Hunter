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


def _spawn_sidecar(tmp_path: Path) -> subprocess.CompletedProcess:
    """Run ``python -m ui.cli.sidecar`` in *tmp_path* and return the result."""
    request = json.dumps(
        {"command": "run_pipeline", "args": {"profile": "Senior Python developer"}}
    )
    return subprocess.run(
        [sys.executable, "-m", "ui.cli.sidecar"],
        input=request + "\n",
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
