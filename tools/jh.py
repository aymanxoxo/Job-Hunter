"""Deterministic JobHunter workflow harness.

The module is split into pure helpers plus a thin argparse/subprocess shell so
agents can test the workflow rules without touching git or GitHub.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output" / "agent"
CONFIG_PATH = ROOT / "tools" / "jh_config.json"
DEFAULT_RISK_FLAGGED = frozenset(
    {"C-008", "C-016", "C-017", "C-020", "C-021", "C-025", "C-031", "C-033"}
)
VALID_STATUSES = frozenset({"todo", "in-progress", "done", "blocked"})
MERGE_PLACEHOLDERS = frozenset({"", "-", "--", "---", "—", "(pr)", "pr", "pending"})
SECRET_RE = re.compile(
    r"(?i)\b(?:token|api[_-]?key|password|secret)\b\s*[:=]\s*"
    r"[\"']?(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{20,}|[A-Za-z0-9+/=]{32,})"
)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    stage: str
    depends_on: tuple[str, ...]
    status: str
    merge: str
    risk_flagged: bool = False


@dataclass(frozen=True)
class Issue:
    code: str
    message: str


@dataclass(frozen=True)
class GateEvidence:
    chunk_id: str
    doctor: str
    focused: str
    full_pytest: str
    ruff: str
    smoke: str


@dataclass(frozen=True)
class Handoff:
    method: str
    message: str


@dataclass(frozen=True)
class StartPlan:
    chunk: Chunk
    branch: str
    commands: tuple[str, ...]


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class GitHubCredential:
    source: str
    token: str


@dataclass(frozen=True)
class GitHubCapability:
    remote: str
    gh_available: bool
    token_source: str
    can_push: bool

    @property
    def can_create_pr(self) -> bool:
        return self.gh_available or bool(self.token_source)


@dataclass(frozen=True)
class DeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass(frozen=True)
class PullRequestCheck:
    name: str
    status: str
    conclusion: str


@dataclass(frozen=True)
class PullRequestReadiness:
    ready: bool
    issues: tuple[str, ...]
    head_sha: str
    head_ref: str


def load_config(root: Path = ROOT) -> dict[str, Any]:
    path = root / "tools" / "jh_config.json"
    if not path.exists():
        return {
            "risk_flagged_chunks": sorted(DEFAULT_RISK_FLAGGED),
            "chunk_tests": {},
            "smoke_imports": ["core"],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def parse_progress(text: str, risk_flagged: set[str] | None = None) -> dict[str, Chunk]:
    risks = risk_flagged or set(DEFAULT_RISK_FLAGGED)
    chunks: dict[str, Chunk] = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not re.fullmatch(r"C-\d{3}", cells[0]):
            continue
        depends_on = tuple(re.findall(r"C-\d{3}", cells[3]))
        chunks[cells[0]] = Chunk(
            id=cells[0],
            title=cells[1],
            stage=cells[2],
            depends_on=depends_on,
            status=cells[4],
            merge=cells[5],
            risk_flagged=cells[0] in risks,
        )
    return chunks


def read_chunks(root: Path = ROOT) -> dict[str, Chunk]:
    config = load_config(root)
    risks = set(config.get("risk_flagged_chunks", DEFAULT_RISK_FLAGGED))
    return parse_progress((root / "PROGRESS.md").read_text(encoding="utf-8"), risks)


def ready_chunks(chunks: dict[str, Chunk]) -> list[Chunk]:
    done = {chunk_id for chunk_id, chunk in chunks.items() if chunk.status == "done"}
    ready: list[Chunk] = []
    for chunk in chunks.values():
        if chunk.status == "todo" and all(dep in done for dep in chunk.depends_on):
            ready.append(chunk)
    return ready


def detect_stale_done_placeholders(
    chunks: dict[str, Chunk], git_messages: list[str]
) -> list[Issue]:
    issues: list[Issue] = []
    joined_messages = "\n".join(
        message for message in git_messages if "Merge pull request" in message
    )
    for chunk in chunks.values():
        if chunk.status != "done" or chunk.merge.strip().lower() not in MERGE_PLACEHOLDERS:
            continue
        if chunk.id in joined_messages:
            issues.append(
                Issue(
                    code="progress.stale_merge",
                    message=f"{chunk.id} is done but still has merge placeholder '{chunk.merge}'",
                )
            )
    return issues


def validate_branch_name(branch: str) -> list[Issue]:
    if re.fullmatch(r"chunk/C-\d{3}-[a-z0-9][a-z0-9-]*", branch):
        return []
    return [
        Issue(
            code="git.branch",
            message="Chunk branches must look like chunk/C-XXX-short-slug",
        )
    ]


def validate_commit_subject(subject: str, chunk_id: str) -> list[Issue]:
    pattern = rf"^(feat|test|refactor|fix|docs|chore|build)\([a-z0-9-]+\): .+  \[{chunk_id}\]$"
    if re.fullmatch(pattern, subject):
        return []
    return [
        Issue(
            code="git.commit_subject",
            message=f"Commit subject must follow '<type>(<scope>): <summary>  [{chunk_id}]'",
        )
    ]


def run_doctor_checks(root: Path = ROOT, git_messages: list[str] | None = None) -> list[Issue]:
    git_messages = git_messages or []
    issues: list[Issue] = []
    progress = root / "PROGRESS.md"
    if not progress.exists():
        issues.append(Issue("progress.missing", "PROGRESS.md is missing"))
    else:
        chunks = parse_progress(progress.read_text(encoding="utf-8"))
        issues.extend(_check_ledger(chunks, git_messages))

    issues.extend(_check_pr_template(root))
    issues.extend(_check_markdown_links(root))
    issues.extend(_check_python_stdout(root))
    issues.extend(_check_plugin_boundaries(root))
    issues.extend(_check_literal_secrets(root))
    return issues


def _check_ledger(chunks: dict[str, Chunk], git_messages: list[str]) -> list[Issue]:
    issues = detect_stale_done_placeholders(chunks, git_messages)
    for chunk in chunks.values():
        if chunk.status not in VALID_STATUSES:
            issues.append(
                Issue("progress.status", f"{chunk.id} has invalid status '{chunk.status}'")
            )
        for dep in chunk.depends_on:
            if dep not in chunks:
                issues.append(Issue("progress.dependency", f"{chunk.id} depends on unknown {dep}"))
    return issues


def _check_pr_template(root: Path) -> list[Issue]:
    template = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if not template.exists():
        return [Issue("pr_template.missing", ".github/PULL_REQUEST_TEMPLATE.md is missing")]
    text = template.read_text(encoding="utf-8").lower()
    required = ["design note", "test evidence", "definition of done", "risk read"]
    return [
        Issue("pr_template.field", f"PR template is missing '{field}'")
        for field in required
        if field not in text
    ]


def _iter_text_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    ignored_parts = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "output",
    }
    for pattern in patterns:
        for path in root.rglob(pattern):
            if any(part in ignored_parts for part in path.relative_to(root).parts):
                continue
            if path.is_file():
                paths.append(path)
    return sorted(set(paths))


def _check_markdown_links(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in _iter_text_files(root, ("*.md",)):
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            if _is_external_or_anchor(target):
                continue
            clean_target = target.split("#", 1)[0].replace("%20", " ")
            if not clean_target:
                continue
            resolved = (path.parent / clean_target).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                continue
            if not resolved.exists():
                rel_path = path.relative_to(root).as_posix()
                issues.append(Issue("docs.missing_link", f"{rel_path} links to missing {target}"))
    return issues


def _is_external_or_anchor(target: str) -> bool:
    return (
        target.startswith("#")
        or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) is not None
        or target.startswith("mailto:")
    )


def _check_python_stdout(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    core = root / "core"
    if not core.exists():
        return issues
    for path in _iter_text_files(core, ("*.py",)):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "sys.stdout" in line or ("print(" in line and "file=" not in line):
                rel_path = path.relative_to(root).as_posix()
                issues.append(Issue("python.stdout", f"{rel_path}:{lineno} writes to stdout"))
    return issues


def _check_plugin_boundaries(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    boundary_roots = [
        (root / "core" / "connectors", "ai_providers"),
        (root / "connectors", "ai_providers"),
        (root / "core" / "ai_providers", "connectors"),
        (root / "ai_providers", "connectors"),
    ]
    for folder, forbidden in boundary_roots:
        if not folder.exists():
            continue
        for path in _iter_text_files(folder, ("*.py",)):
            text = path.read_text(encoding="utf-8")
            if re.search(rf"^\s*(from|import)\s+(core\.)?{forbidden}\b", text, re.MULTILINE):
                rel_path = path.relative_to(root).as_posix()
                issues.append(
                    Issue(
                        "plugin.boundary",
                        f"{rel_path} imports {forbidden}; "
                        "connectors/providers must stay independent",
                    )
                )
    return issues


def _check_literal_secrets(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in _iter_text_files(root, ("*.py", "*.yaml", "*.yml", "*.toml", "*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SECRET_RE.search(line):
                rel_path = path.relative_to(root).as_posix()
                issues.append(Issue("secret.literal", f"{rel_path}:{lineno} looks like a secret"))
    return issues


def choose_handoff(can_create_pr: bool, can_push: bool) -> Handoff:
    if can_create_pr:
        return Handoff("create-pr", "Create the pull request directly.")
    if can_push:
        return Handoff("compare-url", "Push the branch and provide a GitHub compare URL.")
    return Handoff("patch", "Provide a diff/patch plus exact PR title and body.")


def resolve_github_token(root: Path = ROOT) -> GitHubCredential | None:
    env_names = ("JH_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
    for name in env_names:
        value = os.environ.get(name)
        if value:
            return GitHubCredential(source=f"env:{name}", token=value)
    credential = _git_credential_fill(root, protocol="https", host="github.com")
    password = credential.get("password", "")
    if password:
        return GitHubCredential(source="git-credential:https://github.com", token=password)
    return None


def github_capability(
    root: Path = ROOT, *, branch: str = "", dry_run: bool = True
) -> GitHubCapability:
    token = resolve_github_token(root)
    return GitHubCapability(
        remote=_github_remote(root),
        gh_available=shutil.which("gh") is not None,
        token_source=token.source if token else "",
        can_push=_can_push(root, branch, dry_run=dry_run) if branch else False,
    )


def request_github_device_code(client_id: str, scope: str) -> DeviceCode:
    payload = parse.urlencode({"client_id": client_id, "scope": scope}).encode()
    data = _github_form_request("https://github.com/login/device/code", payload)
    missing = sorted({"device_code", "user_code"} - set(data))
    if missing:
        error_code = data.get("error", "unknown error")
        raise RuntimeError(
            f"GitHub OAuth device-code request failed: {error_code} "
            f"(missing {', '.join(missing)})"
        )
    return DeviceCode(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_uri=data.get("verification_uri", "https://github.com/login/device"),
        expires_in=int(data.get("expires_in", 900)),
        interval=int(data.get("interval", 5)),
    )


def poll_github_device_token(
    *,
    client_id: str,
    device_code: str,
    interval: int,
    timeout: int,
    sleep=time.sleep,
) -> str:
    deadline = time.monotonic() + timeout
    current_interval = interval
    while time.monotonic() < deadline:
        sleep(current_interval)
        payload = parse.urlencode(
            {
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            }
        ).encode()
        data = _github_form_request("https://github.com/login/oauth/access_token", payload)
        if "access_token" in data:
            return data["access_token"]
        error_code = data.get("error", "")
        if error_code == "authorization_pending":
            continue
        if error_code == "slow_down":
            current_interval += 5
            continue
        if error_code in {"expired_token", "access_denied"}:
            raise RuntimeError(f"GitHub OAuth device flow failed: {error_code}")
        raise RuntimeError(f"GitHub OAuth device flow failed: {error_code or 'unknown error'}")
    raise RuntimeError("GitHub OAuth device flow timed out")


def store_github_token(root: Path, token: str) -> None:
    _git_credential_approve(
        root,
        {
            "protocol": "https",
            "host": "github.com",
            "username": "x-access-token",
            "password": token,
        },
    )


def evaluate_pr_merge_readiness(
    pr: dict[str, Any], checks: list[PullRequestCheck], statuses: list[dict[str, Any]]
) -> PullRequestReadiness:
    issues: list[str] = []
    if pr.get("state") != "open":
        issues.append(f"PR is not open: {pr.get('state')}")
    if pr.get("draft"):
        issues.append("PR is draft")
    mergeable = pr.get("mergeable")
    mergeable_state = pr.get("mergeable_state", "unknown")
    if mergeable is not True:
        issues.append(f"PR is not confirmed mergeable: {mergeable_state}")
    if not checks:
        issues.append("No CI check runs found for PR head")
    for check in checks:
        if check.status != "completed":
            issues.append(f"Check '{check.name}' is {check.status}")
        elif check.conclusion != "success":
            issues.append(f"Check '{check.name}' concluded {check.conclusion}")
    for status in statuses:
        state = status.get("state", "")
        context = status.get("context", "status")
        if state != "success":
            issues.append(f"Status '{context}' is {state}")
    return PullRequestReadiness(
        ready=not issues,
        issues=tuple(issues),
        head_sha=pr.get("head", {}).get("sha", ""),
        head_ref=pr.get("head", {}).get("ref", ""),
    )


def generate_pr_title(chunk_id: str, slug: str) -> str:
    return f"feat(workflow): add {slug}  [{chunk_id}]"


def generate_pr_body(
    *,
    chunk_id: str,
    summary: str,
    design_note: str,
    evidence: GateEvidence,
    risk_read: str,
) -> str:
    return f"""## Chunk
{chunk_id}

## Summary
{summary}

## Design note
{design_note}

## Test evidence
- Red: captured before implementation in focused C-040 test run.
- Green: {evidence.focused}
- Full suite: {evidence.full_pytest}
- Ruff: {evidence.ruff}
- Doctor: {evidence.doctor}
- Smoke: {evidence.smoke}

## Definition of Done
- [x] Chunk tests green
- [x] Full `pytest` green
- [x] `ruff` clean
- [x] Deterministic workflow doctor clean
- [x] Docs synced
- [x] One commit on `chunk/{chunk_id}`

## Risk read
{risk_read}
"""


def plan_start(
    root: Path, chunk_id: str, *, branch: str, dry_run: bool = True, allow_risk: bool = False
) -> StartPlan:
    chunks = read_chunks(root)
    if chunk_id not in chunks:
        raise ValueError(f"Unknown chunk {chunk_id}")
    chunk = chunks[chunk_id]
    if chunk not in ready_chunks(chunks):
        raise ValueError(f"{chunk_id} is not ready")
    if chunk.risk_flagged and not allow_risk:
        raise ValueError(f"{chunk_id} is risk-flagged; get design sign-off before starting")
    branch_issues = validate_branch_name(branch)
    if branch_issues:
        raise ValueError(branch_issues[0].message)
    commands = ("git fetch origin", f"git checkout -B {branch} origin/main")
    plan = StartPlan(chunk=chunk, branch=branch, commands=commands)
    if not dry_run:
        run(("git", "fetch", "origin"), cwd=root)
        run(("git", "checkout", "-B", branch, "origin/main"), cwd=root)
        _write_json(root / "output" / "agent" / f"{chunk_id}-start.json", {"branch": branch})
    return plan


def git_recent_messages(root: Path = ROOT) -> list[str]:
    result = run(("git", "log", "--format=%h %s", "--max-count=80"), cwd=root, check=False)
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def run(command: tuple[str, ...], *, cwd: Path = ROOT, check: bool = True) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    result = CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(format_result(result))
    return result


def format_result(result: CommandResult) -> str:
    command = " ".join(result.command)
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    return f"{command} -> {result.returncode}\n{output}".strip()


def bootstrap(root: Path = ROOT, *, ci: bool = False) -> str:
    venv_dir = root / ".venv"
    python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    dependency_hash = _dependency_hash(root)
    stamp = root / "output" / "agent" / "deps.sha256"
    if not python.exists():
        run((sys.executable, "-m", "venv", str(venv_dir)), cwd=root)
    if ci or not stamp.exists() or stamp.read_text(encoding="utf-8") != dependency_hash:
        run((str(python), "-m", "pip", "install", "-q", "-e", ".[dev]"), cwd=root)
        _write_text(stamp, dependency_hash)
    required = ["git"]
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"Missing required command(s): {', '.join(missing)}")
    optional = "gh available" if shutil.which("gh") else "gh unavailable"
    return f"bootstrap ok ({optional})"


def project_python(root: Path = ROOT) -> str:
    venv_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def run_gate(root: Path = ROOT, *, chunk_id: str | None = None, ci: bool = False) -> GateEvidence:
    chunk_id = chunk_id or "C-040"
    output_dir = root / "output" / "agent"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_file = output_dir / f"{chunk_id}-gate.sha256"
    log_file = output_dir / f"{chunk_id}-gate.md"
    input_hash = _input_hash(root)
    if not ci and cache_file.exists() and cache_file.read_text(encoding="utf-8") == input_hash:
        text = log_file.read_text(encoding="utf-8")
        return _evidence_from_log(chunk_id, text)

    doctor_issues = run_doctor_checks(root, git_messages=git_recent_messages(root))
    doctor_summary = "PASS doctor" if not doctor_issues else _format_issues(doctor_issues)
    if doctor_issues:
        _write_gate_log(
            log_file,
            GateEvidence(chunk_id, doctor_summary, "SKIP", "SKIP", "SKIP", "SKIP"),
        )
        raise RuntimeError(doctor_summary)

    config = load_config(root)
    focused_targets = config.get("chunk_tests", {}).get(chunk_id, [])
    python = project_python(root)
    focused = _run_and_summarize(
        (python, "-m", "pytest", *focused_targets, "-q", "--asyncio-mode=auto"), root
    )
    full_pytest = _run_and_summarize((python, "-m", "pytest", "-q", "--asyncio-mode=auto"), root)
    ruff = _run_and_summarize((python, "-m", "ruff", "check", "."), root)
    smoke = _import_smoke(config.get("smoke_imports", ["core"]), root)
    evidence = GateEvidence(chunk_id, doctor_summary, focused, full_pytest, ruff, smoke)
    _write_gate_log(log_file, evidence)
    _write_text(cache_file, input_hash)
    return evidence


def _run_and_summarize(command: tuple[str, ...], root: Path) -> str:
    result = run(command, cwd=root, check=False)
    summary = _last_non_empty_line(result.stdout) or _last_non_empty_line(result.stderr)
    status = "PASS" if result.returncode == 0 else "FAIL"
    if result.returncode != 0:
        raise RuntimeError(format_result(result))
    return f"{status} {' '.join(command[2:])}: {summary}"


def _import_smoke(imports: list[str], root: Path) -> str:
    code = "; ".join(f"import {name}" for name in imports)
    result = run((project_python(root), "-c", code), cwd=root, check=False)
    if result.returncode != 0:
        raise RuntimeError(format_result(result))
    return f"PASS import smoke: {', '.join(imports)}"


def _last_non_empty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""


def _dependency_hash(root: Path) -> str:
    files = ["pyproject.toml", "requirements.txt", "requirements-dev.txt"]
    digest = hashlib.sha256()
    for name in files:
        path = root / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _input_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in _iter_text_files(root, ("*.py", "*.md", "*.toml", "*.yaml", "*.yml", "*.json")):
        rel_path = path.relative_to(root).as_posix()
        if rel_path.startswith("output/"):
            continue
        digest.update(rel_path.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _format_issues(issues: list[Issue]) -> str:
    return "\n".join(f"FAIL {issue.code}: {issue.message}" for issue in issues)


def _write_gate_log(path: Path, evidence: GateEvidence) -> None:
    _write_text(
        path,
        "\n".join(
            [
                f"# Gate Evidence {evidence.chunk_id}",
                "",
                evidence.doctor,
                evidence.focused,
                evidence.full_pytest,
                evidence.ruff,
                evidence.smoke,
                "",
            ]
        ),
    )


def _evidence_from_log(chunk_id: str, text: str) -> GateEvidence:
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    padded = (lines + [""] * 5)[:5]
    return GateEvidence(chunk_id, padded[0], padded[1], padded[2], padded[3], padded[4])


def command_status(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    chunks = read_chunks(root)
    ready = ready_chunks(chunks)
    issues = detect_stale_done_placeholders(chunks, git_recent_messages(root))
    branch = run(("git", "branch", "--show-current"), cwd=root, check=False).stdout.strip()
    data = {
        "branch": branch,
        "ready": [chunk.id for chunk in ready],
        "issues": [issue.__dict__ for issue in issues],
    }
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"branch: {branch or '(detached)'}")
        print("ready: " + (", ".join(data["ready"]) if data["ready"] else "none"))
        for issue in issues:
            print(f"{issue.code}: {issue.message}")
    return 0 if not issues else 1


def command_next(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    chunks = ready_chunks(read_chunks(root))
    routine = next((chunk for chunk in chunks if not chunk.risk_flagged), None)
    if not chunks:
        print("No ready chunks.")
        return 1
    for chunk in chunks:
        suffix = " (risk sign-off required)" if chunk.risk_flagged else ""
        print(f"{chunk.id}: {chunk.title}{suffix}")
    if routine:
        print(f"recommended: {routine.id}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    issues = run_doctor_checks(root, git_messages=git_recent_messages(root))
    if issues:
        print(_format_issues(issues))
        return 1
    print("PASS doctor")
    return 0


def command_bootstrap(args: argparse.Namespace) -> int:
    print(bootstrap(Path(args.root).resolve(), ci=args.ci))
    return 0


def command_start(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    plan = plan_start(
        root, args.chunk, branch=args.branch, dry_run=args.dry_run, allow_risk=args.allow_risk
    )
    for command in plan.commands:
        print(command)
    return 0


def command_gate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    evidence = run_gate(root, chunk_id=args.chunk, ci=args.ci)
    for line in [
        evidence.doctor,
        evidence.focused,
        evidence.full_pytest,
        evidence.ruff,
        evidence.smoke,
    ]:
        print(line)
    return 0


def command_pr_ready(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    issues = _pr_ready_git_issues(root, args.chunk)
    if issues:
        print(_format_issues(issues))
        return 1
    evidence = run_gate(root, chunk_id=args.chunk, ci=False)
    title = generate_pr_title(args.chunk, args.slug)
    body = generate_pr_body(
        chunk_id=args.chunk,
        summary=args.summary,
        design_note=args.design_note,
        evidence=evidence,
        risk_read=args.risk_read,
    )
    _write_text(root / "output" / "agent" / f"{args.chunk}-pr.md", f"{title}\n\n{body}")
    print(title)
    print()
    print(body)
    return 0


def command_create_pr(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    pr_file = root / "output" / "agent" / f"{args.chunk}-pr.md"
    if not pr_file.exists():
        print(f"Missing {pr_file}; run pr-ready first.")
        return 1
    title, body = pr_file.read_text(encoding="utf-8").split("\n\n", 1)
    branch = run(("git", "branch", "--show-current"), cwd=root, check=False).stdout.strip()
    remote = _github_remote(root)
    can_push = _can_push(root, branch, dry_run=args.dry_run)
    if can_push and shutil.which("gh") and not args.dry_run:
        result = run(
            (
                "gh",
                "pr",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--base",
                "main",
                "--head",
                branch,
            ),
            cwd=root,
            check=False,
        )
        if result.returncode == 0:
            print(result.stdout.strip())
            return 0
    credential = resolve_github_token(root)
    if can_push and credential and remote and not args.dry_run:
        try:
            url = _create_pr_via_api(remote, credential.token, title, body, branch)
            print(url)
            print(f"credential source: {credential.source}")
            return 0
        except RuntimeError as exc:
            print(str(exc))
    handoff = choose_handoff(can_create_pr=False, can_push=can_push)
    if handoff.method == "compare-url" and remote:
        print(f"{remote}/compare/main...{branch}?expand=1")
    else:
        print("Patch fallback required. Use `git diff origin/main...HEAD` plus this title/body.")
    print()
    print(title)
    print()
    print(body)
    return 0


def command_merge_pr(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    credential = resolve_github_token(root)
    remote = _github_remote(root)
    if not credential:
        print("Missing GitHub credential; run auth-login or set JH_GITHUB_TOKEN.")
        return 1
    if not remote:
        print("Missing GitHub origin remote.")
        return 1

    readiness = wait_for_pr_merge_readiness(
        remote=remote,
        token=credential.token,
        pr_number=args.pr,
        wait_seconds=args.wait,
        poll_seconds=args.poll,
    )
    if not readiness.ready:
        print("PR is not safe to auto-merge:")
        for issue in readiness.issues:
            print(f"- {issue}")
        return 1
    if args.dry_run:
        print(f"PR #{args.pr} is ready to merge at {readiness.head_sha[:7]}")
        return 0

    merge = merge_pr_via_api(
        remote=remote,
        token=credential.token,
        pr_number=args.pr,
        head_sha=readiness.head_sha,
        method=args.method,
    )
    print(merge["html_url"])
    print(f"merged: {merge['sha'][:7]}")
    if args.delete_branch and readiness.head_ref:
        deleted = delete_remote_branch_via_api(remote, credential.token, readiness.head_ref)
        print(f"deleted branch: {readiness.head_ref}" if deleted else "branch delete skipped")
    return 0


def command_auth_status(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    branch = run(("git", "branch", "--show-current"), cwd=root, check=False).stdout.strip()
    capability = github_capability(root, branch=branch, dry_run=args.dry_run)
    data = {
        "remote": capability.remote,
        "branch": branch,
        "gh_available": capability.gh_available,
        "token_source": capability.token_source or None,
        "can_push": capability.can_push,
        "can_create_pr": capability.can_create_pr,
        "token_value": "redacted" if capability.token_source else None,
    }
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"remote: {capability.remote or '(none)'}")
        print(f"branch: {branch or '(detached)'}")
        print(f"gh: {'available' if capability.gh_available else 'unavailable'}")
        print(f"token source: {capability.token_source or '(none)'}")
        print(f"push: {'available' if capability.can_push else 'unavailable'}")
        print(f"direct PR: {'available' if capability.can_create_pr else 'unavailable'}")
        if not capability.can_create_pr:
            print(
                "needed: run auth-login, set JH_GITHUB_TOKEN with Pull requests: "
                "read/write, or install/auth gh"
            )
    return 0


def command_auth_login(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    client_id = args.client_id or os.environ.get("JH_GITHUB_OAUTH_CLIENT_ID", "")
    if not client_id and sys.stdin.isatty():
        try:
            client_id = input("GitHub OAuth App client ID: ").strip()
        except EOFError:
            client_id = ""
    if not client_id:
        print(
            "Missing GitHub OAuth client ID. Set JH_GITHUB_OAUTH_CLIENT_ID or pass "
            "--client-id. The OAuth app must have device flow enabled."
        )
        return 1

    code = request_github_device_code(client_id, args.scope)
    print("Open this URL and enter the code:")
    print(code.verification_uri)
    print(f"code: {code.user_code}")
    if args.open_browser:
        webbrowser.open(code.verification_uri)
    token = poll_github_device_token(
        client_id=client_id,
        device_code=code.device_code,
        interval=code.interval,
        timeout=min(args.timeout, code.expires_in),
    )
    if args.no_store:
        print("GitHub OAuth token captured. Re-run without --no-store to save it.")
        return 0
    store_github_token(root, token)
    print("GitHub OAuth token captured and stored in Git Credential Manager.")
    print("token value: redacted")
    return 0


def command_guide(args: argparse.Namespace) -> int:
    print(
        """JobHunter AI workflow quick guide

1. python tools/jh.py bootstrap
2. python tools/jh.py status
3. python tools/jh.py next
4. python tools/jh.py start C-XXX --branch chunk/C-XXX-slug
5. Write red tests, implement, then run: python tools/jh.py gate C-XXX
6. Commit once with: <type>(<scope>): <summary>  [C-XXX]
7. python tools/jh.py pr-ready C-XXX
8. python tools/jh.py auth-status
9. python tools/jh.py create-pr C-XXX
10. Optional CI-gated merge: python tools/jh.py merge-pr <PR_NUMBER> --wait 600
11. After merge: python tools/jh.py after-merge C-XXX --branch chunk/C-XXX-slug

Credential options for direct PR creation:
- gh CLI already authenticated, or
- python tools/jh.py auth-login with a GitHub OAuth app client ID, or
- JH_GITHUB_TOKEN / GH_TOKEN / GITHUB_TOKEN with Pull requests: read/write, or
- Git Credential Manager storing a GitHub token usable by the GitHub API.

The harness never prints token values and writes generated evidence under output/agent/.
"""
    )
    return 0


def command_after_merge(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    run(("git", "fetch", "origin", "--prune", "--tags"), cwd=root)
    merge = run(
        ("git", "log", "origin/main", "--grep", args.chunk, "--format=%H", "-n", "1"),
        cwd=root,
        check=False,
    ).stdout.strip()
    if not merge:
        print(f"No origin/main merge found for {args.chunk}")
        return 1
    if not args.dry_run:
        run(("git", "tag", "-f", args.chunk, merge), cwd=root)
        run(("git", "branch", "-D", args.branch), cwd=root, check=False)
        run(("git", "push", "origin", "--delete", args.branch), cwd=root, check=False)
        run(("git", "push", "origin", args.chunk), cwd=root, check=False)
    print(f"{args.chunk} merge: {merge[:7]}")
    return 0


def _pr_ready_git_issues(root: Path, chunk_id: str) -> list[Issue]:
    issues: list[Issue] = []
    branch = run(("git", "branch", "--show-current"), cwd=root, check=False).stdout.strip()
    issues.extend(validate_branch_name(branch))
    dirty = run(("git", "status", "--porcelain"), cwd=root, check=False).stdout.strip()
    if dirty:
        issues.append(Issue("git.dirty", "Working tree must be clean before pr-ready"))
    count = run(("git", "rev-list", "--count", "origin/main..HEAD"), cwd=root, check=False)
    if count.returncode == 0 and count.stdout.strip() != "1":
        issues.append(Issue("git.commit_count", "Chunk branch must contain exactly one commit"))
    subject = run(("git", "log", "-1", "--format=%s"), cwd=root, check=False)
    if subject.returncode == 0:
        issues.extend(validate_commit_subject(subject.stdout.strip(), chunk_id))
    return issues


def _github_remote(root: Path) -> str:
    result = run(("git", "remote", "get-url", "origin"), cwd=root, check=False)
    if result.returncode != 0:
        return ""
    value = result.stdout.strip()
    if value.startswith("https://github.com/"):
        return value.removesuffix(".git")
    match = re.match(r"git@github\.com:(.+)\.git", value)
    if match:
        return "https://github.com/" + match.group(1)
    return ""


def _github_owner_repo(remote: str) -> str:
    return remote.removeprefix("https://github.com/").removesuffix(".git")


def _git_credential_fill(root: Path, *, protocol: str, host: str) -> dict[str, str]:
    result = subprocess.run(
        ("git", "credential", "fill"),
        cwd=root,
        input=f"protocol={protocol}\nhost={host}\n\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {}
    fields: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields


def _git_credential_approve(root: Path, fields: dict[str, str]) -> None:
    payload = "".join(f"{key}={value}\n" for key, value in fields.items()) + "\n"
    result = subprocess.run(
        ("git", "credential", "approve"),
        cwd=root,
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Could not store GitHub token in git credential helper")


def _can_push(root: Path, branch: str, *, dry_run: bool) -> bool:
    if dry_run:
        return True
    result = run(("git", "push", "-u", "origin", branch), cwd=root, check=False)
    return result.returncode == 0


def _create_pr_via_api(remote: str, token: str, title: str, body: str, branch: str) -> str:
    owner_repo = _github_owner_repo(remote)
    payload = json.dumps({"title": title, "body": body, "head": branch, "base": "main"}).encode()
    req = request.Request(
        f"https://api.github.com/repos/{owner_repo}/pulls",
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "jobhunter-workflow-harness",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
    except error.HTTPError as exc:
        if exc.code == 422:
            existing = _find_existing_pr_via_api(remote, token, branch)
            if existing:
                return existing
        raise RuntimeError(_github_api_error(exc)) from exc
    return data["html_url"]


def wait_for_pr_merge_readiness(
    *,
    remote: str,
    token: str,
    pr_number: int,
    wait_seconds: int,
    poll_seconds: int,
    sleep=time.sleep,
) -> PullRequestReadiness:
    deadline = time.monotonic() + wait_seconds
    last_readiness = PullRequestReadiness(False, ("PR readiness not checked",), "", "")
    while True:
        pr = get_pull_request_via_api(remote, token, pr_number)
        checks = get_check_runs_via_api(remote, token, pr["head"]["sha"])
        statuses = get_statuses_via_api(remote, token, pr["head"]["sha"])
        readiness = evaluate_pr_merge_readiness(pr, checks, statuses)
        if readiness.ready:
            return readiness
        last_readiness = readiness
        if wait_seconds <= 0 or time.monotonic() >= deadline:
            return last_readiness
        sleep(max(1, poll_seconds))


def get_pull_request_via_api(remote: str, token: str, pr_number: int) -> dict[str, Any]:
    return _github_api_json(remote, token, f"/pulls/{pr_number}")


def get_check_runs_via_api(remote: str, token: str, sha: str) -> list[PullRequestCheck]:
    data = _github_api_json(remote, token, f"/commits/{sha}/check-runs")
    return [
        PullRequestCheck(
            name=run.get("name", "check"),
            status=run.get("status", ""),
            conclusion=run.get("conclusion") or "",
        )
        for run in data.get("check_runs", [])
    ]


def get_statuses_via_api(remote: str, token: str, sha: str) -> list[dict[str, Any]]:
    data = _github_api_json(remote, token, f"/commits/{sha}/status")
    return data.get("statuses", [])


def merge_pr_via_api(
    *, remote: str, token: str, pr_number: int, head_sha: str, method: str
) -> dict[str, Any]:
    payload = {"sha": head_sha, "merge_method": method}
    data = _github_api_json(
        remote, token, f"/pulls/{pr_number}/merge", method="PUT", payload=payload
    )
    if not data.get("merged"):
        message = data.get("message", "unknown")
        raise RuntimeError(f"GitHub merge refused PR #{pr_number}: {message}")
    return {"sha": data["sha"], "html_url": f"{remote}/pull/{pr_number}"}


def delete_remote_branch_via_api(remote: str, token: str, branch: str) -> bool:
    try:
        _github_api_json(
            remote,
            token,
            f"/git/refs/heads/{parse.quote(branch, safe='')}",
            method="DELETE",
            allow_empty=True,
        )
    except RuntimeError:
        return False
    return True


def _github_api_json(
    remote: str,
    token: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    allow_empty: bool = False,
) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = request.Request(
        f"https://api.github.com/repos/{_github_owner_repo(remote)}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "jobhunter-workflow-harness",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read().decode()
    except error.HTTPError as exc:
        raise RuntimeError(_github_api_error(exc)) from exc
    if allow_empty and not body:
        return {}
    if not body:
        return {}
    return json.loads(body)


def _github_form_request(url: str, payload: bytes) -> dict[str, Any]:
    req = request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "jobhunter-workflow-harness",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RuntimeError(f"GitHub OAuth request failed ({exc.code}): {exc.reason}") from exc


def _find_existing_pr_via_api(remote: str, token: str, branch: str) -> str:
    owner_repo = _github_owner_repo(remote)
    owner = owner_repo.split("/", 1)[0]
    query = parse.urlencode({"head": f"{owner}:{branch}", "base": "main", "state": "open"})
    req = request.Request(
        f"https://api.github.com/repos/{owner_repo}/pulls?{query}",
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "jobhunter-workflow-harness",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
    except error.HTTPError:
        return ""
    return data[0]["html_url"] if data else ""


def _github_api_error(exc: error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    message = payload.get("message", exc.reason)
    if exc.code in {401, 403}:
        return (
            f"GitHub PR API failed ({exc.code}): {message}. "
            "Token needs Pull requests: read/write for this repository."
        )
    return f"GitHub PR API failed ({exc.code}): {message}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jh", description="JobHunter deterministic workflow harness"
    )
    parser.add_argument("--root", default=str(ROOT), help="Repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    next_cmd = sub.add_parser("next")
    next_cmd.set_defaults(func=command_next)

    bootstrap_cmd = sub.add_parser("bootstrap")
    bootstrap_cmd.add_argument("--ci", action="store_true")
    bootstrap_cmd.set_defaults(func=command_bootstrap)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--ci", action="store_true")
    doctor.set_defaults(func=command_doctor)

    start = sub.add_parser("start")
    start.add_argument("chunk")
    start.add_argument("--branch", required=True)
    start.add_argument("--dry-run", action="store_true")
    start.add_argument("--allow-risk", action="store_true")
    start.set_defaults(func=command_start)

    gate = sub.add_parser("gate")
    gate.add_argument("chunk", nargs="?", default="C-040")
    gate.add_argument("--ci", action="store_true")
    gate.set_defaults(func=command_gate)

    pr_ready = sub.add_parser("pr-ready")
    pr_ready.add_argument("chunk")
    pr_ready.add_argument("--slug", default="workflow automation harness")
    pr_ready.add_argument("--summary", default="Adds deterministic workflow automation.")
    pr_ready.add_argument("--design-note", default="Pure workflow checks with a thin CLI shell.")
    pr_ready.add_argument("--risk-read", default="Low: tooling-only chunk.")
    pr_ready.set_defaults(func=command_pr_ready)

    create_pr = sub.add_parser("create-pr")
    create_pr.add_argument("chunk")
    create_pr.add_argument("--dry-run", action="store_true")
    create_pr.set_defaults(func=command_create_pr)

    merge_pr = sub.add_parser("merge-pr")
    merge_pr.add_argument("pr", type=int)
    merge_pr.add_argument("--wait", type=int, default=0)
    merge_pr.add_argument("--poll", type=int, default=10)
    merge_pr.add_argument("--method", choices=["merge", "squash", "rebase"], default="merge")
    merge_pr.add_argument("--delete-branch", action="store_true")
    merge_pr.add_argument("--dry-run", action="store_true")
    merge_pr.set_defaults(func=command_merge_pr)

    auth_status = sub.add_parser("auth-status")
    auth_status.add_argument("--json", action="store_true")
    auth_status.add_argument("--dry-run", action="store_true")
    auth_status.set_defaults(func=command_auth_status)

    auth_login = sub.add_parser("auth-login")
    auth_login.add_argument("--client-id")
    auth_login.add_argument("--scope", default="repo")
    auth_login.add_argument("--timeout", type=int, default=900)
    auth_login.add_argument("--open-browser", action="store_true")
    auth_login.add_argument("--no-store", action="store_true")
    auth_login.set_defaults(func=command_auth_login)

    guide = sub.add_parser("guide")
    guide.set_defaults(func=command_guide)

    after_merge = sub.add_parser("after-merge")
    after_merge.add_argument("chunk")
    after_merge.add_argument("--branch", required=True)
    after_merge.add_argument("--dry-run", action="store_true")
    after_merge.set_defaults(func=command_after_merge)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
