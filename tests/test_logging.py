"""C-002 — structured logging & trace core.

Verifies: deterministic JSON record formatting, secret redaction, stderr-only
emission with bound context, run-id generation, and immutable context binding.
"""
import io
import json

from core.logging import Logger, format_record, get_logger, new_run_id, redact


def test_new_run_id_is_unique_hex():
    a, b = new_run_id(), new_run_id()
    assert a != b
    assert len(a) == 32 and int(a, 16) >= 0  # 32-char hex


def test_format_record_is_deterministic_json():
    line = format_record(
        "INFO", "core.test", "hello", {"run_id": "abc", "n": 3}, ts="2026-06-18T00:00:00Z"
    )
    rec = json.loads(line)
    assert rec == {"ts": "2026-06-18T00:00:00Z", "level": "INFO", "logger": "core.test",
                   "msg": "hello", "run_id": "abc", "n": 3}


def test_redact_masks_secret_keys_recursively():
    out = redact({"api_key": "x", "nested": {"Authorization": "Bearer y", "ok": 1}, "name": "z"})
    assert out["api_key"] == "***REDACTED***"
    assert out["nested"]["Authorization"] == "***REDACTED***"
    assert out["nested"]["ok"] == 1 and out["name"] == "z"


def test_format_record_redacts_secrets_in_context():
    rec = json.loads(format_record("INFO", "n", "m", {"token": "sk-123"}, ts="t"))
    assert rec["token"] == "***REDACTED***"


def test_logger_emits_json_to_injected_stream():
    buf = io.StringIO()
    log = Logger("core.test", stream=buf, clock=lambda: "T")
    log.bind(run_id="r1").info("started", step="x")
    rec = json.loads(buf.getvalue().strip())
    assert rec["level"] == "INFO" and rec["msg"] == "started"
    assert rec["run_id"] == "r1" and rec["step"] == "x" and rec["logger"] == "core.test"


def test_bind_is_immutable():
    base = get_logger("n")
    child = base.bind(run_id="r")
    assert base is not child
    assert "run_id" not in base._ctx and child._ctx["run_id"] == "r"


def test_logs_go_to_stderr_not_stdout(capsys):
    get_logger("n").error("boom")
    captured = capsys.readouterr()
    assert captured.out == ""           # never stdout (it is the IPC channel)
    assert json.loads(captured.err.strip())["level"] == "ERROR"
