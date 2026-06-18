"""C-040 deterministic workflow harness."""

import io
from pathlib import Path
from types import SimpleNamespace

from tools import jh

LEDGER = """\
| ID | Title | Stage | Depends on | Status | Merge |
|----|-------|-------|-----------|--------|--------|
| C-004 | Data models | Foundation | C-001 | done | d86d7aa |
| C-005 | BaseConnector ABC | Contracts | C-004 | done | a796edd |
| C-006 | BaseAIProvider ABC | Contracts | C-004 | done | (PR) |
| C-007 | BaseProfileInput ABC + text parser | Contracts | C-004 | todo | - |
| C-008 | Auth strategy resolver | Contracts | C-002, C-003 | todo | - |
| C-009 | Plugin discovery | Contracts | C-005, C-006, C-007 | todo | - |
"""


def test_parse_progress_ledger_and_ready_chunks():
    chunks = jh.parse_progress(LEDGER)
    assert chunks["C-006"].status == "done"
    assert chunks["C-009"].depends_on == ("C-005", "C-006", "C-007")

    ready = jh.ready_chunks(chunks)
    assert [chunk.id for chunk in ready] == ["C-007"]


def test_risk_flagged_chunks_are_reported():
    chunks = jh.parse_progress(LEDGER.replace("C-002, C-003", "C-004"))
    ready = jh.ready_chunks(chunks)

    assert [(chunk.id, chunk.risk_flagged) for chunk in ready] == [
        ("C-007", False),
        ("C-008", True),
    ]


def test_stale_done_merge_placeholder_detects_merged_branch():
    chunks = jh.parse_progress(LEDGER)
    messages = ["914147a Merge pull request #13", "27dd173 Merge pull request #12 from chunk/C-006"]

    issues = jh.detect_stale_done_placeholders(chunks, messages)

    assert issues == [
        jh.Issue(
            code="progress.stale_merge",
            message="C-006 is done but still has merge placeholder '(PR)'",
        )
    ]


def test_doctor_flags_stdout_plugin_boundary_docs_and_credentials(tmp_path):
    (tmp_path / "PROGRESS.md").write_text(LEDGER.replace("(PR)", "27dd173"), encoding="utf-8")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text(
        "## Design note\n## Test evidence\n## Risk read\n", encoding="utf-8"
    )
    core = tmp_path / "core"
    connectors = core / "connectors"
    connectors.mkdir(parents=True)
    (connectors / "bad.py").write_text(
        "from core.ai_providers import BaseAIProvider\nprint('oops')\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("[missing](docs/nope.md)\n", encoding="utf-8")
    fake_secret = "sk-" + "live-secret"
    (tmp_path / "config.yaml").write_text(f'token: "{fake_secret}"\n', encoding="utf-8")

    issues = jh.run_doctor_checks(tmp_path, git_messages=[])

    assert {issue.code for issue in issues} >= {
        "docs.missing_link",
        "python.stdout",
        "plugin.boundary",
        "secret.literal",
    }


def test_pr_body_generation_includes_required_evidence():
    evidence = jh.GateEvidence(
        chunk_id="C-040",
        doctor="PASS doctor",
        focused="PASS focused tests",
        full_pytest="PASS pytest",
        ruff="PASS ruff",
        smoke="PASS import smoke",
    )

    title = jh.generate_pr_title("C-040", "workflow automation harness")
    body = jh.generate_pr_body(
        chunk_id="C-040",
        summary="Adds deterministic workflow automation.",
        design_note="Pure checks plus thin CLI shell.",
        evidence=evidence,
        risk_read="Low: tooling-only chunk.",
    )

    assert title == "feat(workflow): add workflow automation harness  [C-040]"
    assert "## Design note" in body
    assert "PASS focused tests" in body
    assert "PASS pytest" in body
    assert "Low: tooling-only chunk." in body


def test_github_handoff_prefers_pr_then_compare_then_patch():
    assert jh.choose_handoff(can_create_pr=True, can_push=True).method == "create-pr"
    assert jh.choose_handoff(can_create_pr=False, can_push=True).method == "compare-url"
    assert jh.choose_handoff(can_create_pr=False, can_push=False).method == "patch"


def test_github_token_prefers_project_env(monkeypatch):
    monkeypatch.setenv("JH_GITHUB_TOKEN", "token-from-project-env")
    monkeypatch.setenv("GH_TOKEN", "token-from-gh-env")

    credential = jh.resolve_github_token(Path("."))

    assert credential == jh.GitHubCredential(
        source="env:JH_GITHUB_TOKEN", token="token-from-project-env"
    )


def test_github_token_falls_back_to_git_credential(monkeypatch):
    monkeypatch.delenv("JH_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(
        jh,
        "_git_credential_fill",
        lambda root, *, protocol, host: {"password": "token-from-git-credential"},
    )

    credential = jh.resolve_github_token(Path("."))

    assert credential == jh.GitHubCredential(
        source="git-credential:https://github.com", token="token-from-git-credential"
    )


def test_auth_status_json_redacts_token(monkeypatch, capsys):
    monkeypatch.setenv("JH_GITHUB_TOKEN", "super-secret-token")
    monkeypatch.setattr(jh, "_github_remote", lambda root: "https://github.com/acme/repo")
    monkeypatch.setattr(jh, "_can_push", lambda root, branch, dry_run: True)
    monkeypatch.setattr(jh.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        jh,
        "run",
        lambda command, *, cwd=jh.ROOT, check=True: jh.CommandResult(
            command, 0, "chunk/C-040-workflow-automation-harness\n", ""
        ),
    )
    args = type("Args", (), {"root": ".", "json": True, "dry_run": True})()

    assert jh.command_auth_status(args) == 0
    output = capsys.readouterr().out

    assert "super-secret-token" not in output
    assert '"token_value": "redacted"' in output
    assert '"can_create_pr": true' in output


def test_request_github_device_code(monkeypatch):
    monkeypatch.setattr(
        jh,
        "_github_form_request",
        lambda url, payload: {
            "device_code": "device-123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
            "interval": 5,
        },
    )

    code = jh.request_github_device_code("client-id", "repo")

    assert code.user_code == "ABCD-1234"
    assert code.verification_uri == "https://github.com/login/device"


def test_request_github_device_code_missing_fields_has_clear_error(monkeypatch):
    monkeypatch.setattr(
        jh, "_github_form_request", lambda url, payload: {"error": "bad_verification_code"}
    )

    try:
        jh.request_github_device_code("client-id", "repo")
    except RuntimeError as exc:
        assert "device-code request failed: bad_verification_code" in str(exc)
        assert "missing device_code, user_code" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_poll_github_device_token_handles_pending_then_success(monkeypatch):
    responses = iter(
        [
            {"error": "authorization_pending"},
            {"access_token": "oauth-token"},
        ]
    )
    monkeypatch.setattr(jh, "_github_form_request", lambda url, payload: next(responses))
    monkeypatch.setattr(jh.time, "monotonic", iter([0, 1, 2]).__next__)

    token = jh.poll_github_device_token(
        client_id="client-id",
        device_code="device-123",
        interval=0,
        timeout=30,
        sleep=lambda seconds: None,
    )

    assert token == "oauth-token"


def test_github_form_request_parses_json_http_error(monkeypatch):
    def _raise_http_error(req, timeout):
        raise jh.error.HTTPError(
            url="https://github.com/login/oauth/access_token",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(b'{"error": "authorization_pending"}'),
        )

    monkeypatch.setattr(jh.request, "urlopen", _raise_http_error)

    assert jh._github_form_request("https://example.invalid", b"x") == {
        "error": "authorization_pending"
    }


def test_store_github_token_uses_credential_helper(monkeypatch):
    approved = {}
    monkeypatch.setattr(
        jh,
        "_git_credential_approve",
        lambda root, fields: approved.update(fields),
    )

    jh.store_github_token(Path("."), "oauth-token")

    assert approved == {
        "protocol": "https",
        "host": "github.com",
        "username": "x-access-token",
        "password": "oauth-token",
    }


def test_auth_login_stores_token_without_printing_it(monkeypatch, capsys):
    monkeypatch.setattr(
        jh,
        "request_github_device_code",
        lambda client_id, scope: jh.DeviceCode(
            device_code="device-123",
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=0,
        ),
    )
    monkeypatch.setattr(jh, "poll_github_device_token", lambda **kwargs: "oauth-token")
    stored = {}
    monkeypatch.setattr(jh, "store_github_token", lambda root, token: stored.update(token=token))
    args = type(
        "Args",
        (),
        {
            "root": ".",
            "client_id": "client-id",
            "scope": "repo",
            "timeout": 900,
            "open_browser": False,
            "no_store": False,
        },
    )()

    assert jh.command_auth_login(args) == 0
    output = capsys.readouterr().out

    assert stored == {"token": "oauth-token"}
    assert "oauth-token" not in output
    assert "ABCD-1234" in output


def test_auth_login_no_store_message_does_not_reference_missing_flag(monkeypatch, capsys):
    monkeypatch.setattr(
        jh,
        "request_github_device_code",
        lambda client_id, scope: jh.DeviceCode(
            device_code="device-123",
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=0,
        ),
    )
    monkeypatch.setattr(jh, "poll_github_device_token", lambda **kwargs: "oauth-token")
    args = type(
        "Args",
        (),
        {
            "root": ".",
            "client_id": "client-id",
            "scope": "repo",
            "timeout": 900,
            "open_browser": False,
            "no_store": True,
        },
    )()

    assert jh.command_auth_login(args) == 0
    output = capsys.readouterr().out

    assert "--store" not in output
    assert "without --no-store" in output
    assert "oauth-token" not in output


def test_auth_login_missing_client_id_returns_clean_error(monkeypatch, capsys):
    monkeypatch.delenv("JH_GITHUB_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.setattr(jh.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(EOFError()))
    args = type(
        "Args",
        (),
        {
            "root": ".",
            "client_id": "",
            "scope": "repo",
            "timeout": 900,
            "open_browser": False,
            "no_store": False,
        },
    )()

    assert jh.command_auth_login(args) == 1
    output = capsys.readouterr().out

    assert "Missing GitHub OAuth client ID" in output
    assert "Traceback" not in output


def test_project_python_prefers_venv_interpreter(tmp_path):
    relative = Path("Scripts/python.exe") if jh.os.name == "nt" else Path("bin/python")
    expected = tmp_path / ".venv" / relative
    expected.parent.mkdir(parents=True)
    expected.write_text("", encoding="utf-8")

    assert jh.project_python(tmp_path) == str(expected)


def test_import_smoke_uses_project_python(monkeypatch):
    recorded = {}
    monkeypatch.setattr(jh, "project_python", lambda root: "venv-python")

    def _fake_run(command, *, cwd=jh.ROOT, check=True):
        recorded["command"] = command
        return jh.CommandResult(command, 0, "", "")

    monkeypatch.setattr(jh, "run", _fake_run)

    assert jh._import_smoke(["core"], Path(".")) == "PASS import smoke: core"
    assert recorded["command"][0] == "venv-python"


def test_branch_and_commit_validation():
    assert jh.validate_branch_name("chunk/C-040-workflow-automation-harness") == []
    assert jh.validate_commit_subject("feat(workflow): add harness  [C-040]", "C-040") == []

    assert jh.validate_branch_name("feature/harness")
    assert jh.validate_commit_subject("feat: add harness", "C-040")


def test_command_plan_dry_runs_do_not_mutate(tmp_path):
    (tmp_path / "PROGRESS.md").write_text(LEDGER.replace("(PR)", "27dd173"), encoding="utf-8")

    plan = jh.plan_start(tmp_path, "C-007", branch="chunk/C-007-profile-input", dry_run=True)

    assert plan.chunk.id == "C-007"
    assert plan.branch == "chunk/C-007-profile-input"
    assert plan.commands == (
        "git fetch origin",
        "git checkout -B chunk/C-007-profile-input origin/main",
    )


def test_start_blocks_risk_flagged_chunk_without_override(tmp_path):
    ledger = LEDGER.replace("(PR)", "27dd173").replace("C-002, C-003", "C-004")
    (tmp_path / "PROGRESS.md").write_text(ledger, encoding="utf-8")

    try:
        jh.plan_start(
            tmp_path,
            "C-008",
            branch="chunk/C-008-auth-strategy-resolver",
            dry_run=True,
        )
    except ValueError as exc:
        assert "risk-flagged" in str(exc)
        assert "design sign-off" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_start_allows_risk_flagged_chunk_with_override(tmp_path):
    ledger = LEDGER.replace("(PR)", "27dd173").replace("C-002, C-003", "C-004")
    (tmp_path / "PROGRESS.md").write_text(ledger, encoding="utf-8")

    plan = jh.plan_start(
        tmp_path,
        "C-008",
        branch="chunk/C-008-auth-strategy-resolver",
        dry_run=True,
        allow_risk=True,
    )

    assert plan.chunk.id == "C-008"


def test_main_reports_expected_errors_without_traceback(monkeypatch, capsys):
    parser = type(
        "Parser",
        (),
        {
            "parse_args": lambda self, argv: SimpleNamespace(
                func=lambda args: (_ for _ in ()).throw(ValueError("bad input"))
            )
        },
    )
    monkeypatch.setattr(jh, "build_parser", lambda: parser())

    assert jh.main(["start"]) == 1
    captured = capsys.readouterr()

    assert "ERROR: bad input" in captured.err
    assert "Traceback" not in captured.err


def test_ci_workflow_exists_after_chunk_lands():
    assert Path(".github/workflows/ci.yml").is_file()


def test_tools_readme_exists_for_other_agents():
    assert Path("tools/README.md").is_file()
