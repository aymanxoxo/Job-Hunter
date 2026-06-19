"""C-040 deterministic workflow harness."""

import io
import json
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
    assert "- [ ] Auto-merge after CI" in body


def test_pr_body_can_opt_into_auto_merge():
    evidence = jh.GateEvidence(
        chunk_id="C-042",
        doctor="PASS doctor",
        focused="PASS focused tests",
        full_pytest="PASS pytest",
        ruff="PASS ruff",
        smoke="PASS import smoke",
    )

    body = jh.generate_pr_body(
        chunk_id="C-042",
        summary="Adds CI-native auto-merge.",
        design_note="CI job checks opt-in flag.",
        evidence=evidence,
        risk_read="Low.",
        auto_merge=True,
    )

    assert "- [x] Auto-merge after CI" in body


def test_github_handoff_prefers_pr_then_compare_then_patch():
    assert jh.choose_handoff(can_create_pr=True, can_push=True).method == "create-pr"
    assert jh.choose_handoff(can_create_pr=False, can_push=True).method == "compare-url"
    assert jh.choose_handoff(can_create_pr=False, can_push=False).method == "patch"


def _open_pr(**overrides):
    base = {
        "state": "open",
        "draft": False,
        "mergeable": True,
        "mergeable_state": "clean",
        "head": {"sha": "abc1234", "ref": "feature/test"},
    }
    base.update(overrides)
    return base


def test_pr_merge_readiness_allows_open_mergeable_green_pr():
    readiness = jh.evaluate_pr_merge_readiness(
        _open_pr(),
        [jh.PullRequestCheck(name="python", status="completed", conclusion="success")],
        [{"context": "legacy", "state": "success"}],
    )

    assert readiness.ready is True
    assert readiness.issues == ()
    assert readiness.head_sha == "abc1234"


def test_pr_merge_readiness_blocks_pending_failed_and_missing_checks():
    no_checks = jh.evaluate_pr_merge_readiness(_open_pr(), [], [])
    pending = jh.evaluate_pr_merge_readiness(
        _open_pr(),
        [jh.PullRequestCheck(name="python", status="in_progress", conclusion="")],
        [],
    )
    failed = jh.evaluate_pr_merge_readiness(
        _open_pr(),
        [jh.PullRequestCheck(name="python", status="completed", conclusion="failure")],
        [],
    )

    assert no_checks.ready is False
    assert "No CI check runs found for PR head" in no_checks.issues
    assert pending.ready is False
    assert "Check 'python' is in_progress" in pending.issues
    assert failed.ready is False
    assert "Check 'python' concluded failure" in failed.issues


def test_pr_merge_readiness_can_ignore_current_auto_merge_check():
    readiness = jh.evaluate_pr_merge_readiness(
        _open_pr(),
        [
            jh.PullRequestCheck(name="python", status="completed", conclusion="success"),
            jh.PullRequestCheck(name="auto-merge", status="in_progress", conclusion=""),
        ],
        [],
        ignored_checks={"auto-merge"},
    )

    assert readiness.ready is True


def test_pr_merge_readiness_blocks_unmergeable_draft_or_closed_pr():
    closed = jh.evaluate_pr_merge_readiness(
        _open_pr(state="closed"),
        [jh.PullRequestCheck(name="python", status="completed", conclusion="success")],
        [],
    )
    draft = jh.evaluate_pr_merge_readiness(
        _open_pr(draft=True),
        [jh.PullRequestCheck(name="python", status="completed", conclusion="success")],
        [],
    )
    dirty = jh.evaluate_pr_merge_readiness(
        _open_pr(mergeable=False, mergeable_state="dirty"),
        [jh.PullRequestCheck(name="python", status="completed", conclusion="success")],
        [],
    )

    assert "PR is not open: closed" in closed.issues
    assert "PR is draft" in draft.issues
    assert "PR is not confirmed mergeable: dirty" in dirty.issues


def test_pr_auto_merge_opt_in_by_label_or_body_checkbox():
    assert jh.pr_requests_auto_merge({"labels": [{"name": "auto-merge"}], "body": ""})
    assert jh.pr_requests_auto_merge({"labels": [], "body": "- [x] Auto-merge after CI"})
    assert jh.pr_requests_auto_merge({"labels": [], "body": "- [X] Auto-merge after CI"})
    assert not jh.pr_requests_auto_merge({"labels": [], "body": "- [ ] Auto-merge after CI"})


def test_merge_pr_command_dry_run_does_not_merge(monkeypatch, capsys):
    merged = {}
    monkeypatch.setattr(
        jh,
        "resolve_github_token",
        lambda root: jh.GitHubCredential(source="env:JH_GITHUB_TOKEN", token="secret-token"),
    )
    monkeypatch.setattr(jh, "_github_remote", lambda root: "https://github.com/acme/repo")
    monkeypatch.setattr(
        jh,
        "wait_for_pr_merge_readiness",
        lambda **kwargs: jh.PullRequestReadiness(True, (), "abc1234", "feature/test"),
    )
    monkeypatch.setattr(jh, "merge_pr_via_api", lambda **kwargs: merged.update(kwargs))
    args = SimpleNamespace(
        root=".",
        pr=15,
        wait=0,
        poll=10,
        method="merge",
        delete_branch=False,
        dry_run=True,
    )

    assert jh.command_merge_pr(args) == 0
    output = capsys.readouterr().out

    assert "ready to merge" in output
    assert merged == {}


def test_merge_pr_command_blocks_not_ready(monkeypatch, capsys):
    monkeypatch.setattr(
        jh,
        "resolve_github_token",
        lambda root: jh.GitHubCredential(source="env:JH_GITHUB_TOKEN", token="secret-token"),
    )
    monkeypatch.setattr(jh, "_github_remote", lambda root: "https://github.com/acme/repo")
    monkeypatch.setattr(
        jh,
        "wait_for_pr_merge_readiness",
        lambda **kwargs: jh.PullRequestReadiness(
            False, ("Check 'python' is queued",), "abc1234", ""
        ),
    )
    args = SimpleNamespace(
        root=".",
        pr=15,
        wait=0,
        poll=10,
        method="merge",
        delete_branch=False,
        dry_run=False,
    )

    assert jh.command_merge_pr(args) == 1
    output = capsys.readouterr().out

    assert "PR is not safe to auto-merge" in output
    assert "Check 'python' is queued" in output


def test_merge_pr_command_merges_with_head_sha_and_can_delete_branch(monkeypatch, capsys):
    calls = {}
    monkeypatch.setattr(
        jh,
        "resolve_github_token",
        lambda root: jh.GitHubCredential(source="env:JH_GITHUB_TOKEN", token="secret-token"),
    )
    monkeypatch.setattr(jh, "_github_remote", lambda root: "https://github.com/acme/repo")
    monkeypatch.setattr(
        jh,
        "wait_for_pr_merge_readiness",
        lambda **kwargs: jh.PullRequestReadiness(True, (), "abc1234", "feature/test"),
    )

    def _merge(**kwargs):
        calls["merge"] = kwargs
        return {"html_url": "https://github.com/acme/repo/pull/15", "sha": "def5678"}

    monkeypatch.setattr(jh, "merge_pr_via_api", _merge)
    monkeypatch.setattr(
        jh,
        "delete_remote_branch_via_api",
        lambda remote, token, branch: calls.setdefault("deleted", branch) or True,
    )
    args = SimpleNamespace(
        root=".",
        pr=15,
        wait=0,
        poll=10,
        method="merge",
        delete_branch=True,
        dry_run=False,
    )

    assert jh.command_merge_pr(args) == 0
    output = capsys.readouterr().out

    assert "https://github.com/acme/repo/pull/15" in output
    assert calls["merge"]["head_sha"] == "abc1234"
    assert calls["deleted"] == "feature/test"


def test_ci_auto_merge_skips_without_pr_event(monkeypatch, tmp_path, capsys):
    event = tmp_path / "event.json"
    event.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
    args = SimpleNamespace(
        label="auto-merge",
        body_flag="Auto-merge after CI",
        wait=0,
        poll=10,
        method="merge",
        ignore_check=["auto-merge"],
        delete_branch=True,
    )

    assert jh.command_ci_auto_merge(args) == 0
    assert "event is not a pull_request" in capsys.readouterr().out


def test_ci_auto_merge_skips_without_opt_in(monkeypatch, tmp_path, capsys):
    event = tmp_path / "event.json"
    event.write_text('{"pull_request": {"number": 18}}', encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
    monkeypatch.setattr(
        jh,
        "get_pull_request_via_api",
        lambda remote, token, pr_number: _open_pr(labels=[], body="- [ ] Auto-merge after CI"),
    )
    args = SimpleNamespace(
        label="auto-merge",
        body_flag="Auto-merge after CI",
        wait=0,
        poll=10,
        method="merge",
        ignore_check=["auto-merge"],
        delete_branch=True,
    )

    assert jh.command_ci_auto_merge(args) == 0
    assert "did not opt in" in capsys.readouterr().out


def test_ci_auto_merge_merges_opted_in_green_pr(monkeypatch, tmp_path, capsys):
    event = tmp_path / "event.json"
    event.write_text('{"pull_request": {"number": 18}}', encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
    calls = {}
    monkeypatch.setattr(
        jh,
        "get_pull_request_via_api",
        lambda remote, token, pr_number: _open_pr(labels=[{"name": "auto-merge"}]),
    )
    monkeypatch.setattr(
        jh,
        "wait_for_pr_merge_readiness",
        lambda **kwargs: jh.PullRequestReadiness(True, (), "abc1234", "feature/test"),
    )
    monkeypatch.setattr(
        jh,
        "merge_pr_via_api",
        lambda **kwargs: (
            calls.setdefault("merge", kwargs),
            {"sha": "def5678", "html_url": "https://github.com/acme/repo/pull/18"},
        )[1],
    )
    monkeypatch.setattr(
        jh,
        "delete_remote_branch_via_api",
        lambda remote, token, branch: calls.setdefault("deleted", branch) or True,
    )
    args = SimpleNamespace(
        label="auto-merge",
        body_flag="Auto-merge after CI",
        wait=600,
        poll=10,
        method="merge",
        ignore_check=["auto-merge"],
        delete_branch=True,
    )

    assert jh.command_ci_auto_merge(args) == 0
    output = capsys.readouterr().out

    assert "CI auto-merged PR #18" in output
    assert calls["merge"]["head_sha"] == "abc1234"
    assert calls["deleted"] == "feature/test"


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


# --- C-043: async-by-default + idempotent long-running ops (ADR-023) ---


def test_clamp_wait_seconds_bounds_the_wait():
    assert jh.clamp_wait_seconds(600) == jh.MAX_WAIT_SECONDS
    assert jh.clamp_wait_seconds(-5) == 0
    assert jh.clamp_wait_seconds(120) == 120


def test_pr_already_merged_detected():
    assert jh.pr_already_merged({"merged": True}) is True
    assert jh.pr_already_merged({"state": "closed", "merged_at": "2026-06-18T00:00:00Z"}) is True
    assert jh.pr_already_merged(_open_pr()) is False


def test_wait_short_circuits_on_already_merged_without_polling(monkeypatch):
    calls = {"pr": 0}

    def fake_get_pr(remote, token, pr_number):
        calls["pr"] += 1
        return {"merged": True, "head": {"sha": "abc1234", "ref": "chunk/C-043"}}

    def boom(*args, **kwargs):
        raise AssertionError("must not poll checks/statuses or sleep on a merged PR")

    monkeypatch.setattr(jh, "get_pull_request_via_api", fake_get_pr)
    monkeypatch.setattr(jh, "get_check_runs_via_api", boom)
    monkeypatch.setattr(jh, "get_statuses_via_api", boom)

    readiness = jh.wait_for_pr_merge_readiness(
        remote="https://github.com/acme/repo",
        token="t",
        pr_number=9,
        wait_seconds=600,
        poll_seconds=10,
        sleep=boom,
    )

    assert readiness.already_merged is True
    assert readiness.ready is False
    assert calls["pr"] == 1


def test_merge_pr_already_merged_is_idempotent(monkeypatch, capsys):
    deletes = []
    merged = {}
    monkeypatch.setattr(
        jh,
        "resolve_github_token",
        lambda root: jh.GitHubCredential(source="env", token="t"),
    )
    monkeypatch.setattr(jh, "_github_remote", lambda root: "https://github.com/acme/repo")
    monkeypatch.setattr(
        jh,
        "wait_for_pr_merge_readiness",
        lambda **kwargs: jh.PullRequestReadiness(
            False, ("PR already merged",), "abc1234", "chunk/C-043", already_merged=True
        ),
    )
    monkeypatch.setattr(jh, "merge_pr_via_api", lambda **kwargs: merged.update(kwargs))
    monkeypatch.setattr(
        jh,
        "delete_remote_branch_via_api",
        lambda remote, token, branch: deletes.append(branch) or True,
    )
    args = SimpleNamespace(
        root=".",
        pr=9,
        wait=600,
        poll=10,
        method="merge",
        ignore_check=[],
        delete_branch=True,
        dry_run=False,
    )

    assert jh.command_merge_pr(args) == 0
    out = capsys.readouterr().out
    assert "already merged" in out
    assert merged == {}
    assert deletes == ["chunk/C-043"]


def test_maybe_delete_branch_reports_already_absent(monkeypatch, capsys):
    monkeypatch.setattr(jh, "delete_remote_branch_via_api", lambda remote, token, branch: False)
    jh._maybe_delete_branch("https://github.com/acme/repo", "t", "chunk/gone", delete=True)
    out = capsys.readouterr().out
    assert "already absent" in out


def test_merge_pr_clamps_excessive_wait(monkeypatch, capsys):
    seen = {}

    def fake_wait(**kwargs):
        seen["wait_seconds"] = kwargs["wait_seconds"]
        return jh.PullRequestReadiness(False, ("Check 'python' is queued",), "abc1234", "b")

    monkeypatch.setattr(
        jh, "resolve_github_token", lambda root: jh.GitHubCredential(source="env", token="t")
    )
    monkeypatch.setattr(jh, "_github_remote", lambda root: "https://github.com/acme/repo")
    monkeypatch.setattr(jh, "wait_for_pr_merge_readiness", fake_wait)
    args = SimpleNamespace(
        root=".",
        pr=9,
        wait=600,
        poll=10,
        method="merge",
        ignore_check=[],
        delete_branch=False,
        dry_run=False,
    )

    jh.command_merge_pr(args)
    assert seen["wait_seconds"] == jh.MAX_WAIT_SECONDS


def test_pr_status_reports_merged(monkeypatch, capsys):
    monkeypatch.setattr(
        jh, "resolve_github_token", lambda root: jh.GitHubCredential(source="env", token="t")
    )
    monkeypatch.setattr(jh, "_github_remote", lambda root: "https://github.com/acme/repo")
    monkeypatch.setattr(
        jh,
        "wait_for_pr_merge_readiness",
        lambda **kwargs: jh.PullRequestReadiness(
            False, ("PR already merged",), "abc1234", "b", already_merged=True
        ),
    )
    args = SimpleNamespace(root=".", pr=9, json=True, ignore_check=[])

    assert jh.command_pr_status(args) == 0
    out = capsys.readouterr().out.lower()
    assert '"merged": true' in out
    assert '"state": "merged"' in out


def test_pr_status_reports_pending(monkeypatch, capsys):
    monkeypatch.setattr(
        jh, "resolve_github_token", lambda root: jh.GitHubCredential(source="env", token="t")
    )
    monkeypatch.setattr(jh, "_github_remote", lambda root: "https://github.com/acme/repo")
    monkeypatch.setattr(
        jh,
        "wait_for_pr_merge_readiness",
        lambda **kwargs: jh.PullRequestReadiness(
            False, ("Check 'python' is queued",), "abc1234", "b"
        ),
    )
    args = SimpleNamespace(root=".", pr=9, json=False, ignore_check=[])

    assert jh.command_pr_status(args) == 0
    out = capsys.readouterr().out
    assert "pending" in out
    assert "queued" in out


def test_pr_status_command_is_registered():
    parser = jh.build_parser()
    args = parser.parse_args(["pr-status", "9", "--json"])
    assert args.func is jh.command_pr_status
    assert args.pr == 9


# --- C-045: chunk registry single source of truth (ADR-024) ---

REGISTRY_FIXTURE = {
    "smoke_imports": ["core"],
    "chunks": {
        "C-001": {
            "title": "Scaffold",
            "stage": "Foundation",
            "depends_on": [],
            "risk_flagged": False,
            "tests": [],
        },
        "C-008": {
            "title": "Auth resolver",
            "stage": "Contracts",
            "depends_on": ["C-001"],
            "risk_flagged": True,
            "tests": ["tests/test_auth.py"],
        },
    },
}

DEV_PLAN_OK = (
    "| ID | Goal | Files | Depends on | Acceptance | SDD ref |\n"
    "| C-001 | x | y | — | a | §1 |\n"
    "| C-008 | x | y | C-001 | a | §1 |\n"
)


def _consistent_ledger():
    return {
        "C-001": jh.Chunk("C-001", "Scaffold", "Foundation", (), "done", "abc", False),
        "C-008": jh.Chunk("C-008", "Auth resolver", "Contracts", ("C-001",), "todo", "—", True),
    }


def _write_registry(tmp_path, registry):
    (tmp_path / "tools").mkdir(exist_ok=True)
    (tmp_path / "tools" / "chunks.json").write_text(json.dumps(registry), encoding="utf-8")


def test_load_registry_reads_chunks_json(tmp_path):
    _write_registry(tmp_path, REGISTRY_FIXTURE)
    reg = jh.load_registry(tmp_path)
    assert reg["chunks"]["C-008"]["risk_flagged"] is True
    assert reg["smoke_imports"] == ["core"]


def test_load_config_derives_from_registry(tmp_path):
    _write_registry(tmp_path, REGISTRY_FIXTURE)
    cfg = jh.load_config(tmp_path)
    assert cfg["risk_flagged_chunks"] == ["C-008"]
    assert cfg["chunk_tests"] == {"C-008": ["tests/test_auth.py"]}
    assert cfg["smoke_imports"] == ["core"]


def test_registry_consistency_passes_when_aligned():
    assert jh.check_registry_consistency(REGISTRY_FIXTURE, _consistent_ledger(), DEV_PLAN_OK) == []


def test_registry_consistency_flags_ledger_dependency_mismatch():
    ledger = _consistent_ledger()
    ledger["C-008"] = jh.Chunk(
        "C-008", "Auth resolver", "Contracts", ("C-001", "C-005"), "todo", "—", True
    )
    issues = jh.check_registry_consistency(REGISTRY_FIXTURE, ledger, DEV_PLAN_OK)
    assert any(i.code == "registry.depends" and "C-008" in i.message for i in issues)


def test_registry_consistency_flags_risk_mismatch():
    ledger = _consistent_ledger()
    ledger["C-008"] = jh.Chunk(
        "C-008", "Auth resolver", "Contracts", ("C-001",), "todo", "—", False
    )
    issues = jh.check_registry_consistency(REGISTRY_FIXTURE, ledger, DEV_PLAN_OK)
    assert any(i.code == "registry.risk" and "C-008" in i.message for i in issues)


def test_registry_consistency_flags_devplan_dependency_mismatch():
    bad_plan = DEV_PLAN_OK.replace("| C-008 | x | y | C-001 |", "| C-008 | x | y | — |")
    issues = jh.check_registry_consistency(REGISTRY_FIXTURE, _consistent_ledger(), bad_plan)
    assert any(i.code == "registry.devplan_depends" and "C-008" in i.message for i in issues)


def test_registry_consistency_flags_sdd_anchor_mismatch():
    registry = json.loads(json.dumps(REGISTRY_FIXTURE))
    registry["chunks"]["C-008"]["sdd_anchor"] = "§9.9"
    plan = DEV_PLAN_OK.replace(
        "| C-008 | x | y | C-001 | a | Â§1 |",
        "| C-008 | x | y | C-001 | a | §8.1 |",
    )

    issues = jh.check_registry_consistency(registry, _consistent_ledger(), plan)

    assert any(i.code == "registry.sdd_anchor" and "C-008" in i.message for i in issues)


def test_registry_consistency_expands_dev_plan_ranges():
    registry = {
        "smoke_imports": ["core"],
        "chunks": {
            "C-010": {"title": "a", "stage": "AI", "depends_on": [],
                      "risk_flagged": False, "tests": []},
            "C-011": {"title": "b", "stage": "AI", "depends_on": [],
                      "risk_flagged": False, "tests": []},
            "C-014": {"title": "f", "stage": "AI", "depends_on": ["C-010", "C-011"],
                      "risk_flagged": False, "tests": []},
        },
    }
    ledger = {
        "C-010": jh.Chunk("C-010", "a", "AI", (), "todo", "—", False),
        "C-011": jh.Chunk("C-011", "b", "AI", (), "todo", "—", False),
        "C-014": jh.Chunk("C-014", "f", "AI", ("C-010", "C-011"), "todo", "—", False),
    }
    plan = (
        "| ID | Goal | Files | Depends on | Acceptance | SDD ref |\n"
        "| C-010 | a | f | — | x | §1 |\n"
        "| C-011 | b | f | — | x | §1 |\n"
        "| C-014 | f | f | C-010–C-011 | x | §1 |\n"
    )
    assert jh.check_registry_consistency(registry, ledger, plan) == []


def test_real_registry_matches_ledger_and_doctor_passes():
    reg = jh.load_registry()
    ledger = jh.read_chunks()
    assert set(reg["chunks"]) == set(ledger)
    issues = jh.check_registry_consistency(
        reg,
        ledger,
        (jh.ROOT / "Documents" / "JobHunter_DEV_PLAN_v1.0.md").read_text(encoding="utf-8"),
    )
    assert issues == []


def test_jh_config_json_is_absorbed_into_registry():
    assert not (jh.ROOT / "tools" / "jh_config.json").exists()


# --- C-044: generic engine decoupled from project business (ADR-025) ---

from tools import jh_engine as engine  # noqa: E402
from tools import jh_project  # noqa: E402

DEMO_PROJECT = jh_project.ProjectConfig(
    name="Demo",
    progress_filename="TASKS.md",
    registry_relpath="meta/tasks.json",
    dev_plan_relpath="docs/PLAN.md",
    sdd_relpath="docs/SDD.md",
    decisions_relpath="docs/DECISIONS.md",
    pr_template_relpath=".github/PR.md",
    output_agent_relpath="out/agent",
    source_check_dir="src",
    chunk_id_regex=r"T-\d{2}",
    branch_regex=r"task/T-\d{2}-[a-z0-9-]+",
    default_risk_flagged=frozenset({"T-02"}),
    default_smoke_imports=("src",),
    plugin_boundaries=(("src/a", "b"),),
    test_command_tail=("-m", "unittest"),
    test_flags=("-v",),
    lint_command_tail=("-m", "flake8"),
    default_gate_chunk="T-01",
    orientation_start_marker="<!-- demo:orientation:start -->",
    orientation_end_marker="<!-- demo:orientation:end -->",
    orientation_prelude_lines=("- **Phase:** Demo.",),
    orientation_footer_lines=("- **Protocol:** Demo.",),
    orientation_recent_done=2,
    module_agent_paths=(("src", "src/AGENTS.md"),),
    stage_agent_paths=(("Build", "src/AGENTS.md"),),
    cli_prog="demo",
    cli_description="Demo workflow",
    guide_text="demo guide",
    forbidden_engine_identifiers=("Demo",),
)

DEMO_LEDGER = """\
| ID | Title | Stage | Depends on | Status | Merge |
|----|-------|-------|-----------|--------|--------|
| T-01 | First task | Setup | — | done | abc1234 |
| T-02 | Risky task | Build | T-01 | todo | - |
| T-03 | Next task | Build | T-01 | todo | - |
"""


def test_engine_runs_status_next_against_a_non_jobhunter_adapter():
    # status: parse the ledger with the Demo id format + risk set (no JobHunter values)
    chunks = engine.parse_ledger(
        DEMO_LEDGER,
        risk_flagged=set(DEMO_PROJECT.default_risk_flagged),
        id_pattern=DEMO_PROJECT.chunk_id_regex,
    )
    assert set(chunks) == {"T-01", "T-02", "T-03"}
    assert chunks["T-02"].risk_flagged is True
    assert chunks["T-02"].depends_on == ("T-01",)

    # next: ready chunks resolve purely from the parsed graph
    ready = [chunk.id for chunk in engine.ready_chunks(chunks)]
    assert ready == ["T-02", "T-03"]


def test_engine_gate_plan_uses_adapter_supplied_tools():
    commands = engine.gate_commands(
        python="py",
        focused_targets=["tests/test_demo.py"],
        test_command_tail=DEMO_PROJECT.test_command_tail,
        test_flags=DEMO_PROJECT.test_flags,
        lint_command_tail=DEMO_PROJECT.lint_command_tail,
    )
    assert commands["full"] == ("py", "-m", "unittest", "-v")
    assert commands["lint"] == ("py", "-m", "flake8")
    assert "pytest" not in " ".join(commands["focused"])


def test_engine_module_has_no_jobhunter_identifiers():
    source = (jh.ROOT / "tools" / "jh_engine.py").read_text(encoding="utf-8")
    leaked = engine.find_project_identifiers(
        source, jh_project.JOBHUNTER.forbidden_engine_identifiers
    )
    assert leaked == []


def test_doctor_flags_engine_purity_violation(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "jh_engine.py").write_text(
        "# leaked JobHunter and PROGRESS.md\n", encoding="utf-8"
    )
    issues = jh._check_engine_purity(tmp_path)
    assert {i.code for i in issues} == {"engine.purity"}
    assert any("JobHunter" in i.message for i in issues)


# --- C-046: generated PROGRESS orientation + merge-hash sync ---


def test_engine_renders_orientation_from_chunk_graph():
    chunks = {
        "T-01": engine.Chunk("T-01", "One", "Setup", (), "done", "aaa1111", False),
        "T-02": engine.Chunk("T-02", "Two", "Build", ("T-01",), "done", "bbb2222", False),
        "T-03": engine.Chunk("T-03", "Three", "Build", ("T-02",), "todo", "-", False),
        "T-04": engine.Chunk("T-04", "Four", "Build", ("T-02",), "blocked", "-", True),
    }

    orientation = engine.compute_orientation(chunks, recent_done_limit=2)
    rendered = engine.render_orientation(
        orientation,
        prelude_lines=("- **Phase:** Demo phase.",),
        footer_lines=("- **Protocol:** Demo protocol.",),
    )

    assert rendered == "\n".join(
        [
            "- **Phase:** Demo phase.",
            "- **Last done:** **T-02** - Two (`bbb2222`). "
            "Prior done: **T-01** - One (`aaa1111`).",
            "- **Next ready:** **T-03** - Three.",
            "- **Blocked:** **T-04** - Four (risk-flagged; design sign-off required).",
            "- **Protocol:** Demo protocol.",
        ]
    )


SYNC_PROGRESS = """\
# PROGRESS

## Orientation

<!-- jh:orientation:start -->
- stale manual text
<!-- jh:orientation:end -->

## Ledger

| ID | Title | Stage | Depends on | Status | Merge |
|----|-------|-------|-----------|--------|--------|
| C-001 | One | Setup | - | done | aaa1111 |
| C-002 | Two | Build | C-001 | done | (PR) |
| C-003 | Three | Build | C-002 | todo | - |
"""


def test_sync_progress_rewrites_orientation_and_backfills_merge_hash(tmp_path):
    progress = tmp_path / "PROGRESS.md"
    progress.write_text(SYNC_PROGRESS, encoding="utf-8")

    changed = jh.sync_progress(tmp_path, merge_hashes={"C-002": "bbb2222"})

    text = progress.read_text(encoding="utf-8")
    assert changed is True
    assert "- stale manual text" not in text
    assert "| C-002 | Two | Build | C-001 | done | bbb2222 |" in text
    assert "- **Last done:** **C-002** - Two (`bbb2222`)." in text
    assert "- **Next ready:** **C-003** - Three." in text


def test_doctor_flags_stale_orientation_and_passes_after_sync(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text(
        "## Design note\n## Test evidence\n## Definition of Done\n## Risk read\n",
        encoding="utf-8",
    )
    (tmp_path / "PROGRESS.md").write_text(
        SYNC_PROGRESS.replace("(PR)", "bbb2222"), encoding="utf-8"
    )

    issues = jh.run_doctor_checks(tmp_path, git_messages=[], merge_hashes={})
    assert any(issue.code == "progress.orientation_stale" for issue in issues)

    assert jh.sync_progress(tmp_path, merge_hashes={}) is True
    issues = jh.run_doctor_checks(tmp_path, git_messages=[], merge_hashes={})
    assert not any(issue.code == "progress.orientation_stale" for issue in issues)


def test_parse_chunk_merge_log_ignores_docs_sync_and_uses_chunk_merge_body():
    log_text = (
        "ddd4444\x1fMerge pull request #23 from owner/docs/C-007-merge-sync\n\n"
        "docs(progress): record C-007 merge hash\n\x1e"
        "ccc3333\x1fMerge pull request #22 from owner/chunk/C-007-base-profile-input\n\n"
        "feat(profile): add profile input  [C-007]\n\x1e"
    )

    assert jh.parse_chunk_merge_log(log_text) == {"C-007": "ccc3333"}


def test_sync_command_is_registered():
    parser = jh.build_parser()
    args = parser.parse_args(["sync"])
    assert args.func is jh.command_sync


def test_after_merge_invokes_progress_sync(monkeypatch, tmp_path, capsys):
    synced = []

    def fake_run(command, *, cwd=jh.ROOT, check=True):
        if command[:3] == ("git", "log", "origin/main"):
            return jh.CommandResult(command, 0, "abcdef1234567890\n", "")
        return jh.CommandResult(command, 0, "", "")

    monkeypatch.setattr(jh, "run", fake_run)
    monkeypatch.setattr(jh, "sync_progress", lambda root: synced.append(root) or True)
    args = SimpleNamespace(
        root=str(tmp_path),
        chunk="C-046",
        branch="chunk/C-046-progress-sync",
        dry_run=False,
    )

    assert jh.command_after_merge(args) == 0
    assert synced == [tmp_path]
    assert "synced PROGRESS.md" in capsys.readouterr().out


# --- C-047: one-command chunk context brief ---


def test_engine_renders_chunk_brief_with_optional_gate_absent():
    brief = engine.ChunkBrief(
        chunk_id="T-02",
        title="Risky task",
        stage="Build",
        status="todo",
        files=("src/task.py",),
        depends_on=("T-01",),
        risk_flagged=True,
        tests=("tests/test_task.py",),
        sdd_anchor="S-1",
        sdd_excerpt="## S-1\nSpec text.",
        adr_titles=("ADR-001 - First decision",),
        agents_path="src/AGENTS.md",
        gate_evidence=None,
    )

    rendered = engine.render_chunk_brief(brief)
    data = engine.chunk_brief_to_dict(brief)

    assert "T-02 - Risky task" in rendered
    assert "Risk flagged: yes" in rendered
    assert "tests/test_task.py" in rendered
    assert "## S-1" in rendered
    assert "ADR-001 - First decision" in rendered
    assert "Gate evidence: not found" in rendered
    assert data["chunk"]["id"] == "T-02"
    assert data["gate_evidence"] is None


def test_context_c007_prints_complete_brief_with_sdd_and_missing_gate(capsys):
    args = SimpleNamespace(root=str(jh.ROOT), chunk="C-007", json=False)

    assert jh.command_context(args) == 0
    output = capsys.readouterr().out

    assert "C-007 - BaseProfileInput ABC + text parser" in output
    assert "Stage: Contracts" in output
    assert "Risk flagged: no" in output
    assert "Tests:" in output
    assert "tests/test_profile_inputs.py" in output
    assert "### 3.3 Profile Input (new)" in output
    assert "### 5.3 Profile Input layer (new)" in output
    assert "core/profile_inputs/AGENTS.md" in output
    assert "Gate evidence: not found" in output


def test_context_json_emits_structured_fields(capsys):
    args = SimpleNamespace(root=str(jh.ROOT), chunk="C-007", json=True)

    assert jh.command_context(args) == 0
    data = json.loads(capsys.readouterr().out)

    assert data["chunk"]["id"] == "C-007"
    assert data["chunk"]["status"] == "done"
    assert data["chunk"]["risk_flagged"] is False
    assert data["chunk"]["depends_on"] == ["C-004"]
    assert data["metadata"]["sdd_anchor"] == "§3.3, §5.3"
    assert "Profile Input" in data["sdd_excerpt"]
    assert data["agents_path"].endswith("core/profile_inputs/AGENTS.md")
    assert data["gate_evidence"] is None


def test_context_command_is_registered():
    parser = jh.build_parser()
    args = parser.parse_args(["context", "C-007", "--json"])

    assert args.func is jh.command_context
    assert args.chunk == "C-007"
    assert args.json is True
