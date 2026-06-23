"""Generic workflow engine — project-agnostic core for the chunk/TDD/gate/PR loop.

This module holds the reusable workflow logic and value types. It contains **no**
project-specific knowledge (no file names, gate commands, id formats, or project
identifiers) — everything project-specific is supplied by a ProjectConfig adapter
(see tools/jh_project.py) and passed in as parameters. `jh.py doctor` enforces this
purity via `find_project_identifiers` (ADR-025).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

VALID_STATUSES = frozenset({"todo", "in-progress", "done", "blocked"})
MERGE_PLACEHOLDERS = frozenset({"", "-", "--", "---", "—", "(pr)", "pr", "pending"})
MAX_WAIT_SECONDS = 300


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
class FocusedTestCommand:
    command: tuple[str, ...]
    cwd_relpath: str


@dataclass(frozen=True)
class FocusedTestPlan:
    commands: tuple[FocusedTestCommand, ...]
    unsupported_targets: tuple[str, ...]
    config_errors: tuple[str, ...]


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
    already_merged: bool = False


@dataclass(frozen=True)
class Orientation:
    recent_done: tuple[Chunk, ...]
    next_ready: tuple[Chunk, ...]
    blocked: tuple[Chunk, ...]


@dataclass(frozen=True)
class ChunkBrief:
    chunk_id: str
    title: str
    stage: str
    status: str
    files: tuple[str, ...]
    depends_on: tuple[str, ...]
    risk_flagged: bool
    tests: tuple[str, ...]
    sdd_anchor: str
    sdd_excerpt: str
    adr_titles: tuple[str, ...]
    agents_path: str
    gate_evidence: str | None = None


def clamp_wait_seconds(seconds: int, *, maximum: int = MAX_WAIT_SECONDS) -> int:
    """Bound a requested wait so no agent-facing op can block unbounded (ADR-023)."""
    return max(0, min(seconds, maximum))


def pr_already_merged(pr: dict[str, Any]) -> bool:
    """True when the PR is already merged, so merge/delete can no-op idempotently."""
    if pr.get("merged") is True:
        return True
    return pr.get("state") == "closed" and bool(pr.get("merged_at"))


def find_ids(text: str, id_pattern: str) -> list[str]:
    """All chunk ids in a string, per the project's id pattern."""
    return re.findall(id_pattern, text)


def parse_ledger(text: str, *, risk_flagged: set[str], id_pattern: str) -> dict[str, Chunk]:
    """Parse a markdown ledger table into Chunks. Id format is supplied by the adapter."""
    chunks: dict[str, Chunk] = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not re.fullmatch(id_pattern, cells[0]):
            continue
        depends_on = tuple(re.findall(id_pattern, cells[3]))
        chunks[cells[0]] = Chunk(
            id=cells[0],
            title=cells[1],
            stage=cells[2],
            depends_on=depends_on,
            status=cells[4],
            merge=cells[5],
            risk_flagged=cells[0] in risk_flagged,
        )
    return chunks


def ready_chunks(chunks: dict[str, Chunk]) -> list[Chunk]:
    done = {chunk_id for chunk_id, chunk in chunks.items() if chunk.status == "done"}
    ready: list[Chunk] = []
    for chunk in chunks.values():
        if chunk.status == "todo" and all(dep in done for dep in chunk.depends_on):
            ready.append(chunk)
    return ready


def compute_orientation(
    chunks: dict[str, Chunk], *, recent_done_limit: int = 3
) -> Orientation:
    """Compute generated progress orientation from an ordered chunk graph."""
    done = [chunk for chunk in chunks.values() if chunk.status == "done"]
    blocked = [chunk for chunk in chunks.values() if chunk.status == "blocked"]
    limit = max(0, recent_done_limit)
    return Orientation(
        recent_done=tuple(reversed(done[-limit:])) if limit else (),
        next_ready=tuple(ready_chunks(chunks)),
        blocked=tuple(blocked),
    )


def render_orientation(
    orientation: Orientation,
    *,
    prelude_lines: tuple[str, ...] = (),
    footer_lines: tuple[str, ...] = (),
) -> str:
    """Render a deterministic Markdown orientation block."""
    lines = list(prelude_lines)
    lines.append(_render_recent_done(orientation.recent_done))
    lines.append(_render_chunk_list("Next ready", orientation.next_ready))
    lines.append(_render_chunk_list("Blocked", orientation.blocked))
    lines.extend(footer_lines)
    return "\n".join(lines)


def _render_recent_done(chunks: tuple[Chunk, ...]) -> str:
    if not chunks:
        return "- **Last done:** none."
    head, *tail = chunks
    line = f"- **Last done:** {_render_chunk(head)}."
    if tail:
        prior = "; ".join(_render_chunk(chunk) for chunk in tail)
        line += f" Prior done: {prior}."
    return line


def _render_chunk_list(label: str, chunks: tuple[Chunk, ...]) -> str:
    if not chunks:
        return f"- **{label}:** none."
    rendered = "; ".join(_render_chunk(chunk) for chunk in chunks)
    return f"- **{label}:** {rendered}."


def _render_chunk(chunk: Chunk) -> str:
    text = f"**{chunk.id}** - {chunk.title}"
    if chunk.merge.strip().lower() not in MERGE_PLACEHOLDERS:
        text += f" (`{chunk.merge}`)"
    elif chunk.status == "done":
        text += " (merge pending)"
    if chunk.risk_flagged and chunk.status != "done":
        text += " (risk-flagged; design sign-off required)"
    return text


def render_chunk_brief(brief: ChunkBrief) -> str:
    """Render a human-readable chunk context brief from already-loaded inputs."""
    lines = [
        f"# Chunk Context: {brief.chunk_id} - {brief.title}",
        "",
        "## Metadata",
        f"- Stage: {brief.stage}",
        f"- Status: {brief.status}",
        f"- Risk flagged: {'yes' if brief.risk_flagged else 'no'}",
        f"- Dependencies: {_render_values(brief.depends_on)}",
        f"- Files: {_render_values(brief.files)}",
        f"- Tests: {_render_values(brief.tests)}",
        f"- SDD anchor: {brief.sdd_anchor or 'not configured'}",
        f"- Module guide: {brief.agents_path or 'not found'}",
        "",
        "## Relevant ADRs",
        _render_values(brief.adr_titles),
        "",
        "## SDD Excerpt",
        brief.sdd_excerpt or "No SDD excerpt found.",
        "",
        "## Gate Evidence",
        brief.gate_evidence or "Gate evidence: not found",
    ]
    return "\n".join(lines).rstrip() + "\n"


def chunk_brief_to_dict(brief: ChunkBrief) -> dict[str, Any]:
    """Return the machine-readable form used by the context command's JSON mode."""
    return {
        "chunk": {
            "id": brief.chunk_id,
            "title": brief.title,
            "stage": brief.stage,
            "status": brief.status,
            "depends_on": list(brief.depends_on),
            "risk_flagged": brief.risk_flagged,
        },
        "metadata": {
            "files": list(brief.files),
            "tests": list(brief.tests),
            "sdd_anchor": brief.sdd_anchor,
        },
        "sdd_excerpt": brief.sdd_excerpt,
        "adr_titles": list(brief.adr_titles),
        "agents_path": brief.agents_path,
        "gate_evidence": brief.gate_evidence,
    }


def _render_values(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def render_pr_comments(comments: list[dict[str, Any]]) -> str:
    """Render PR review threads + issue comments for human reading."""
    if not comments:
        return "No review or issue comments."
    lines: list[str] = []
    for comment in comments:
        kind = comment.get("kind", "comment")
        user = comment.get("user") or "unknown"
        path = comment.get("path")
        location = f" ({path})" if path else ""
        body = (comment.get("body") or "").strip()
        lines.append(f"- [{kind}] {user}{location}: {body}")
    return "\n".join(lines)


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


def validate_branch_name(branch: str, *, pattern: str) -> list[Issue]:
    if re.fullmatch(pattern, branch):
        return []
    return [
        Issue(
            code="git.branch",
            message="Branch must match the configured chunk-branch pattern",
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


def choose_handoff(can_create_pr: bool, can_push: bool) -> Handoff:
    if can_create_pr:
        return Handoff("create-pr", "Create the pull request directly.")
    if can_push:
        return Handoff("compare-url", "Push the branch and provide a GitHub compare URL.")
    return Handoff("patch", "Provide a diff/patch plus exact PR title and body.")


def evaluate_pr_merge_readiness(
    pr: dict[str, Any],
    checks: list[PullRequestCheck],
    statuses: list[dict[str, Any]],
    ignored_checks: set[str] | None = None,
) -> PullRequestReadiness:
    issues: list[str] = []
    ignored_checks = ignored_checks or set()
    effective_checks = [check for check in checks if check.name not in ignored_checks]
    if pr.get("state") != "open":
        issues.append(f"PR is not open: {pr.get('state')}")
    if pr.get("draft"):
        issues.append("PR is draft")
    mergeable = pr.get("mergeable")
    mergeable_state = pr.get("mergeable_state", "unknown")
    if mergeable is not True:
        issues.append(f"PR is not confirmed mergeable: {mergeable_state}")
    if not effective_checks:
        issues.append("No CI check runs found for PR head")
    for check in effective_checks:
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


def pr_requests_auto_merge(
    pr: dict[str, Any],
    *,
    label: str = "auto-merge",
    body_flag: str = "Auto-merge after CI",
) -> bool:
    labels = {
        item.get("name", "").strip().lower()
        for item in pr.get("labels", [])
        if isinstance(item, dict)
    }
    if label.lower() in labels:
        return True
    body = pr.get("body") or ""
    flag_re = re.compile(rf"- \[[xX]\]\s*{re.escape(body_flag)}")
    return flag_re.search(body) is not None


def gate_commands(
    *,
    python: str,
    test_command_tail: tuple[str, ...],
    test_flags: tuple[str, ...],
    lint_command_tail: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    """Build the gate command tuples from adapter-supplied tool invocations."""
    return {
        "full": (python, *test_command_tail, *test_flags),
        "lint": (python, *lint_command_tail),
    }


def focused_test_plan(
    *,
    python: str,
    focused_targets: list[str],
    test_command_tail: tuple[str, ...],
    test_flags: tuple[str, ...],
    frontend_root_relpath: str,
    frontend_test_command: tuple[str, ...],
    frontend_test_extensions: tuple[str, ...],
    rust_root_relpath: str,
    rust_test_command: tuple[str, ...],
    rust_test_extensions: tuple[str, ...],
) -> FocusedTestPlan:
    """Split focused test targets into project-supplied runner commands."""
    python_targets: list[str] = []
    frontend_targets: list[str] = []
    rust_targets: list[str] = []
    unsupported: list[str] = []
    config_errors: list[str] = []
    frontend_prefix = _normalized_prefix(frontend_root_relpath)
    rust_tests_prefix = _normalized_prefix(f"{rust_root_relpath}/tests")
    frontend_extensions = _lower_extensions(frontend_test_extensions)
    rust_extensions = _lower_extensions(rust_test_extensions)

    for target in focused_targets:
        normalized = target.replace("\\", "/")
        lower = normalized.lower()
        if lower.endswith(frontend_extensions):
            frontend_targets.append(_strip_prefix(normalized, frontend_prefix))
        elif lower.endswith(rust_extensions):
            rust_targets.append(_rust_test_name(_strip_prefix(normalized, rust_tests_prefix)))
        elif lower.endswith(".py"):
            python_targets.append(target)
        else:
            unsupported.append(target)

    commands: list[FocusedTestCommand] = []
    if python_targets or not (frontend_targets or rust_targets or unsupported):
        commands.append(
            FocusedTestCommand(
                command=(python, *test_command_tail, *python_targets, *test_flags),
                cwd_relpath=".",
            )
        )
    if frontend_targets:
        if frontend_test_command:
            commands.append(
                FocusedTestCommand(
                    command=(*frontend_test_command, *frontend_targets),
                    cwd_relpath=frontend_root_relpath,
                )
            )
        else:
            config_errors.append("frontend focused tests are configured but no command is set")
    if rust_targets:
        if rust_test_command:
            for rust_target in rust_targets:
                commands.append(
                    FocusedTestCommand(
                        command=(*rust_test_command, rust_target),
                        cwd_relpath=rust_root_relpath,
                    )
                )
        else:
            config_errors.append("Rust focused tests are configured but no command is set")
    return FocusedTestPlan(
        commands=tuple(commands),
        unsupported_targets=tuple(unsupported),
        config_errors=tuple(config_errors),
    )


def _normalized_prefix(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    return f"{normalized}/" if normalized else ""


def _lower_extensions(extensions: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(ext.lower() for ext in extensions) or ("\0",)


def _strip_prefix(path: str, prefix: str) -> str:
    return path.removeprefix(prefix) if prefix and path.startswith(prefix) else path


def _rust_test_name(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return name.removesuffix(".rs")


def find_project_identifiers(source: str, forbidden: tuple[str, ...]) -> list[str]:
    """Return any forbidden project-specific tokens found in engine source (purity guard)."""
    return [token for token in forbidden if token in source]
