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
from pathlib import Path
from typing import Any
from urllib import error, parse, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import jh_engine as engine  # noqa: E402
from tools import jh_project  # noqa: E402
from tools.jh_engine import (  # noqa: E402
    MAX_WAIT_SECONDS,
    VALID_STATUSES,
    Chunk,
    CommandResult,
    DeviceCode,
    GateEvidence,
    GitHubCapability,
    GitHubCredential,
    Issue,
    PullRequestCheck,
    PullRequestReadiness,
    StartPlan,
    choose_handoff,
    clamp_wait_seconds,
    detect_stale_done_placeholders,
    evaluate_pr_merge_readiness,
    gate_commands,
    pr_already_merged,
    pr_requests_auto_merge,
    ready_chunks,
    validate_commit_subject,
)

PROJECT = jh_project.JOBHUNTER
DEFAULT_RISK_FLAGGED = PROJECT.default_risk_flagged


def parse_progress(text, risk_flagged=None):
    risks = risk_flagged or set(PROJECT.default_risk_flagged)
    return engine.parse_ledger(text, risk_flagged=risks, id_pattern=PROJECT.chunk_id_regex)


def validate_branch_name(branch):
    return engine.validate_branch_name(branch, pattern=PROJECT.branch_regex)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output" / "agent"
CONFIG_PATH = ROOT / "tools" / "jh_config.json"
REGISTRY_PATH = ROOT / "tools" / "chunks.json"
SECRET_RE = re.compile(
    r"(?i)\b(?:token|api[_-]?key|password|secret)\b\s*[:=]\s*"
    r"[\"']?(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{20,}|[A-Za-z0-9+/=]{32,})"
)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")






























def load_registry(root: Path = ROOT) -> dict[str, Any]:
    """Load the chunk registry (tools/chunks.json) — the single source of truth for
    per-chunk static metadata (stage, deps, risk, tests) and global smoke imports."""
    path = root / PROJECT.registry_relpath
    if not path.exists():
        return {"smoke_imports": list(PROJECT.default_smoke_imports), "chunks": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("smoke_imports", list(PROJECT.default_smoke_imports))
    data.setdefault("chunks", {})
    return data


def load_config(root: Path = ROOT) -> dict[str, Any]:
    """Back-compat config view derived from the registry, so existing callers keep
    the legacy {risk_flagged_chunks, chunk_tests, smoke_imports} shape (ADR-024)."""
    registry = load_registry(root)
    meta = registry.get("chunks", {})
    if not meta:
        return {
            "risk_flagged_chunks": sorted(DEFAULT_RISK_FLAGGED),
            "chunk_tests": {},
            "smoke_imports": registry.get("smoke_imports", list(PROJECT.default_smoke_imports)),
        }
    return {
        "risk_flagged_chunks": sorted(cid for cid, m in meta.items() if m.get("risk_flagged")),
        "chunk_tests": {cid: m["tests"] for cid, m in meta.items() if m.get("tests")},
        "smoke_imports": registry.get("smoke_imports", list(PROJECT.default_smoke_imports)),
    }


def expand_dep_ids(cell: str) -> set[str]:
    """Extract chunk ids from a dependency cell, expanding `C-0AA-C-0BB` ranges."""
    ids: set[str] = set()
    for match in re.finditer(r"C-(\d{3})\s*[–—]\s*(?:C-)?(\d{3})", cell):
        for number in range(int(match.group(1)), int(match.group(2)) + 1):
            ids.add(f"C-{number:03d}")
    stripped = re.sub(r"C-\d{3}\s*[–—]\s*(?:C-)?\d{3}", " ", cell)
    ids.update(re.findall(r"C-\d{3}", stripped))
    return ids


def parse_dev_plan_deps(text: str) -> dict[str, set[str]]:
    """Map chunk id -> dependency id set for every row in the dev-plan section 10 tables."""
    deps: dict[str, set[str]] = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not re.fullmatch(r"C-\d{3}", cells[0]):
            continue
        deps[cells[0]] = expand_dep_ids(cells[3])
    return deps


def parse_dev_plan_chunks(text: str) -> dict[str, dict[str, Any]]:
    """Extract per-chunk file and SDD-ref metadata from dev-plan section 10 rows."""
    chunks: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not re.fullmatch(PROJECT.chunk_id_regex, cells[0]):
            continue
        chunks[cells[0]] = {
            "goal": cells[1],
            "files": list(_extract_plan_files(cells[2])),
            "sdd_anchor": cells[5],
        }
    return chunks


def _extract_plan_files(cell: str) -> tuple[str, ...]:
    files = re.findall(r"`([^`]+)`", cell)
    if files:
        return tuple(files)
    cleaned = cell.strip()
    if not cleaned or cleaned in {"-", "--", "---", "â€”", "—"}:
        return ()
    return (cleaned,)


def check_registry_consistency(
    registry: dict[str, Any],
    ledger_chunks: dict[str, Chunk],
    dev_plan_text: str,
) -> list[Issue]:
    """Assert the registry, the PROGRESS ledger, and dev-plan section 10 agree (ADR-024)."""
    issues: list[Issue] = []
    meta = registry.get("chunks", {})
    reg_ids, led_ids = set(meta), set(ledger_chunks)
    for cid in sorted(led_ids - reg_ids):
        issues.append(
            Issue("registry.missing", f"{cid} is in the ledger but not tools/chunks.json")
        )
    for cid in sorted(reg_ids - led_ids):
        issues.append(
            Issue("registry.extra", f"{cid} is in tools/chunks.json but not the ledger")
        )
    for cid in sorted(reg_ids & led_ids):
        entry, chunk = meta[cid], ledger_chunks[cid]
        if entry.get("stage") != chunk.stage:
            issues.append(
                Issue("registry.stage", f"{cid} stage differs between registry and ledger")
            )
        if entry.get("title") != chunk.title:
            issues.append(
                Issue("registry.title", f"{cid} title differs between registry and ledger")
            )
        if tuple(entry.get("depends_on", [])) != chunk.depends_on:
            issues.append(
                Issue("registry.depends", f"{cid} dependencies differ from the ledger")
            )
        if bool(entry.get("risk_flagged", False)) != chunk.risk_flagged:
            issues.append(
                Issue("registry.risk", f"{cid} risk flag differs between registry and ledger")
            )
    dev_deps = parse_dev_plan_deps(dev_plan_text)
    dev_meta = parse_dev_plan_chunks(dev_plan_text)
    dev_ids = set(dev_deps)
    for cid in sorted(dev_ids - reg_ids):
        issues.append(
            Issue("registry.devplan_extra", f"{cid} is in dev-plan but not the registry")
        )
    for cid in sorted(dev_ids & reg_ids):
        reg_dep = set(meta[cid].get("depends_on", [])) & dev_ids
        if reg_dep != (dev_deps[cid] & dev_ids):
            issues.append(
                Issue(
                    "registry.devplan_depends",
                    f"{cid} dependencies differ between registry and dev plan",
                )
            )
        entry = meta[cid]
        if "sdd_anchor" in entry and entry.get("sdd_anchor", "") != dev_meta[cid]["sdd_anchor"]:
            issues.append(
                Issue(
                    "registry.sdd_anchor",
                    f"{cid} SDD anchor differs between registry and dev plan",
                )
            )
        if "files" in entry and tuple(entry.get("files", [])) != tuple(dev_meta[cid]["files"]):
            issues.append(
                Issue(
                    "registry.files",
                    f"{cid} files differ between registry and dev plan",
                )
            )
    return issues




def ordered_chunks_from_registry(
    chunks: dict[str, Chunk], registry: dict[str, Any] | None = None
) -> dict[str, Chunk]:
    """Return chunks in registry order, preserving any ledger-only rows at the end."""
    registry = registry or {}
    ordered: dict[str, Chunk] = {}
    for cid in registry.get("chunks", {}):
        if cid in chunks:
            ordered[cid] = chunks[cid]
    for cid, chunk in chunks.items():
        if cid not in ordered:
            ordered[cid] = chunk
    return ordered


def read_chunks(root: Path = ROOT) -> dict[str, Chunk]:
    config = load_config(root)
    risks = set(config.get("risk_flagged_chunks", DEFAULT_RISK_FLAGGED))
    text = (root / PROJECT.progress_filename).read_text(encoding="utf-8")
    return ordered_chunks_from_registry(parse_progress(text, risks), load_registry(root))


def render_generated_orientation(chunks: dict[str, Chunk]) -> str:
    orientation = engine.compute_orientation(
        chunks, recent_done_limit=PROJECT.orientation_recent_done
    )
    return engine.render_orientation(
        orientation,
        prelude_lines=PROJECT.orientation_prelude_lines,
        footer_lines=PROJECT.orientation_footer_lines,
    )


def replace_generated_orientation(progress_text: str, orientation: str) -> str:
    start = PROJECT.orientation_start_marker
    end = PROJECT.orientation_end_marker
    start_at = progress_text.find(start)
    if start_at == -1:
        raise ValueError(f"Missing generated orientation start marker: {start}")
    end_at = progress_text.find(end, start_at + len(start))
    if end_at == -1:
        raise ValueError(f"Missing generated orientation end marker: {end}")
    prefix = progress_text[: start_at + len(start)]
    suffix = progress_text[end_at:]
    return f"{prefix}\n{orientation.rstrip()}\n{suffix.lstrip()}"


def backfill_progress_merges(progress_text: str, merge_hashes: dict[str, str]) -> str:
    lines = progress_text.splitlines()
    updated: list[str] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and re.fullmatch(PROJECT.chunk_id_regex, cells[0]):
            cid, status, merge = cells[0], cells[4], cells[5]
            if status == "done" and merge.strip().lower() in engine.MERGE_PLACEHOLDERS:
                if cid in merge_hashes:
                    cells[5] = merge_hashes[cid]
                    line = "| " + " | ".join(cells[:6]) + " |"
        updated.append(line)
    ending = "\n" if progress_text.endswith("\n") else ""
    return "\n".join(updated) + ending


def sync_progress_text(
    root: Path, progress_text: str, *, merge_hashes: dict[str, str] | None = None
) -> str:
    hashes = merge_hashes if merge_hashes is not None else git_merge_hashes_by_chunk(root)
    backfilled = backfill_progress_merges(progress_text, hashes)
    config = load_config(root)
    risks = set(config.get("risk_flagged_chunks", DEFAULT_RISK_FLAGGED))
    chunks = ordered_chunks_from_registry(parse_progress(backfilled, risks), load_registry(root))
    return replace_generated_orientation(backfilled, render_generated_orientation(chunks))


def sync_progress(root: Path = ROOT, *, merge_hashes: dict[str, str] | None = None) -> bool:
    progress = root / PROJECT.progress_filename
    original = progress.read_text(encoding="utf-8")
    updated = sync_progress_text(root, original, merge_hashes=merge_hashes)
    if updated == original:
        return False
    progress.write_text(updated, encoding="utf-8")
    return True


def check_generated_orientation(
    root: Path, progress_text: str, *, merge_hashes: dict[str, str] | None = None
) -> list[Issue]:
    try:
        expected = sync_progress_text(root, progress_text, merge_hashes=merge_hashes)
    except ValueError as exc:
        return [Issue("progress.orientation_markers", str(exc))]
    if expected != progress_text:
        return [
            Issue(
                "progress.orientation_stale",
                f"{PROJECT.progress_filename} generated orientation is stale; run `jh.py sync`",
            )
        ]
    return []


def parse_chunk_merge_log(log_text: str) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for record in log_text.split("\x1e"):
        if not record.strip() or "\x1f" not in record:
            continue
        full_hash, body = record.split("\x1f", 1)
        full_hash = full_hash.strip()
        tagged = re.findall(rf"\[({PROJECT.chunk_id_regex})\]", body)
        branch_ids = re.findall(rf"\bchunk/({PROJECT.chunk_id_regex})\b", body)
        for cid in tagged or branch_ids:
            hashes.setdefault(cid, full_hash[:7])
    return hashes


def git_merge_hashes_by_chunk(root: Path = ROOT) -> dict[str, str]:
    result = run(
        ("git", "log", "--merges", "--format=%H%x1f%B%x1e", "--max-count=400"),
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return {}
    return parse_chunk_merge_log(result.stdout)


def build_chunk_context(root: Path, chunk_id: str) -> engine.ChunkBrief:
    registry = load_registry(root)
    chunks = read_chunks(root)
    if chunk_id not in chunks:
        raise ValueError(f"Unknown chunk {chunk_id}")

    dev_meta = _dev_plan_metadata(root).get(chunk_id, {})
    meta = registry.get("chunks", {}).get(chunk_id, {})
    chunk = chunks[chunk_id]
    files = tuple(meta.get("files") or dev_meta.get("files", ()))
    tests = tuple(meta.get("tests", ()))
    sdd_anchor = str(meta.get("sdd_anchor") or dev_meta.get("sdd_anchor", ""))
    sdd_excerpt = extract_sdd_excerpt(_read_optional(root / PROJECT.sdd_relpath), sdd_anchor)
    decisions_text = _read_optional(root / PROJECT.decisions_relpath)
    return engine.ChunkBrief(
        chunk_id=chunk.id,
        title=chunk.title,
        stage=chunk.stage,
        status=chunk.status,
        files=files,
        depends_on=chunk.depends_on,
        risk_flagged=chunk.risk_flagged,
        tests=tests,
        sdd_anchor=sdd_anchor,
        sdd_excerpt=sdd_excerpt,
        adr_titles=relevant_adr_titles(decisions_text, sdd_anchor),
        agents_path=resolve_agents_path(root, files, chunk.stage),
        gate_evidence=read_gate_evidence(root, chunk_id),
    )


def _dev_plan_metadata(root: Path) -> dict[str, dict[str, Any]]:
    dev_plan = root / PROJECT.dev_plan_relpath
    if not dev_plan.exists():
        return {}
    return parse_dev_plan_chunks(dev_plan.read_text(encoding="utf-8"))


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def extract_sdd_excerpt(sdd_text: str, sdd_anchor: str) -> str:
    sections = [
        section
        for ref in extract_sdd_refs(sdd_anchor)
        if (section := extract_markdown_section(sdd_text, ref))
    ]
    return "\n\n".join(sections)


def extract_sdd_refs(sdd_anchor: str) -> tuple[str, ...]:
    refs = []
    for match in re.finditer(r"§\s*(\d+(?:\.\d+)*)", sdd_anchor):
        refs.append(match.group(1))
    return tuple(refs)


def extract_markdown_section(text: str, section_ref: str) -> str:
    if not text:
        return ""
    match = re.search(
        rf"^(?P<hashes>##+)\s+{re.escape(section_ref)}(?:\s|$).*",
        text,
        re.MULTILINE,
    )
    if not match:
        return ""
    level = len(match.group("hashes"))
    next_heading = re.search(rf"^#{{2,{level}}}\s+", text[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.start() : end].strip()


def relevant_adr_titles(decisions_text: str, sdd_anchor: str) -> tuple[str, ...]:
    titles = parse_adr_titles(decisions_text)
    refs = tuple(dict.fromkeys(re.findall(r"ADR-\d{3}", sdd_anchor)))
    return tuple(f"{ref} - {titles[ref]}" for ref in refs if ref in titles)


def parse_adr_titles(decisions_text: str) -> dict[str, str]:
    titles: dict[str, str] = {}
    for match in re.finditer(r"^## (ADR-\d{3})\s+(?:—|-)\s+(.+)$", decisions_text, re.MULTILINE):
        titles[match.group(1)] = match.group(2).strip()
    return titles


def resolve_agents_path(root: Path, files: tuple[str, ...], stage: str) -> str:
    for file_path in files:
        normalized = file_path.replace("\\", "/")
        for prefix, agents_path in PROJECT.module_agent_paths:
            if normalized == prefix or normalized.startswith(prefix.rstrip("/") + "/"):
                return agents_path if (root / agents_path).exists() else ""
    for stage_name, agents_path in PROJECT.stage_agent_paths:
        if stage == stage_name:
            return agents_path if (root / agents_path).exists() else ""
    root_agents = "AGENTS.md"
    return root_agents if (root / root_agents).exists() else ""


def read_gate_evidence(root: Path, chunk_id: str) -> str | None:
    gate_log = root / PROJECT.output_agent_relpath / f"{chunk_id}-gate.md"
    if not gate_log.exists():
        return None
    return gate_log.read_text(encoding="utf-8").strip()












def _check_engine_purity(root: Path) -> list[Issue]:
    engine_path = root / "tools" / "jh_engine.py"
    if not engine_path.exists():
        return []
    leaked = engine.find_project_identifiers(
        engine_path.read_text(encoding="utf-8"), PROJECT.forbidden_engine_identifiers
    )
    return [
        Issue("engine.purity", f"tools/jh_engine.py leaks project identifier '{token}'")
        for token in leaked
    ]


def run_doctor_checks(
    root: Path = ROOT,
    git_messages: list[str] | None = None,
    merge_hashes: dict[str, str] | None = None,
) -> list[Issue]:
    git_messages = git_messages or []
    issues: list[Issue] = []
    progress = root / PROJECT.progress_filename
    if not progress.exists():
        issues.append(Issue("progress.missing", "PROGRESS.md is missing"))
    else:
        progress_text = progress.read_text(encoding="utf-8")
        chunks = parse_progress(progress_text)
        issues.extend(_check_ledger(chunks, git_messages))
        issues.extend(check_generated_orientation(root, progress_text, merge_hashes=merge_hashes))
        if (root / PROJECT.registry_relpath).exists():
            dev_plan = root / PROJECT.dev_plan_relpath
            dev_text = dev_plan.read_text(encoding="utf-8") if dev_plan.exists() else ""
            issues.extend(check_registry_consistency(load_registry(root), chunks, dev_text))

    issues.extend(_check_pr_template(root))
    issues.extend(_check_markdown_links(root))
    issues.extend(_check_python_stdout(root))
    issues.extend(_check_plugin_boundaries(root))
    issues.extend(_check_literal_secrets(root))
    issues.extend(_check_engine_purity(root))
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
    template = root / PROJECT.pr_template_relpath
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
    core = root / PROJECT.source_check_dir
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
        (root / subpath, forbidden) for subpath, forbidden in PROJECT.plugin_boundaries
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






def generate_pr_title(chunk_id: str, slug: str) -> str:
    return f"feat(workflow): add {slug}  [{chunk_id}]"


def generate_pr_body(
    *,
    chunk_id: str,
    summary: str,
    design_note: str,
    evidence: GateEvidence,
    risk_read: str,
    auto_merge: bool = False,
) -> str:
    auto_merge_checkbox = "x" if auto_merge else " "
    return f"""## Chunk
{chunk_id}

## Summary
{summary}

## Design note
{design_note}

## Test evidence
- Red: captured before implementation in focused {chunk_id} test run.
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

## Merge policy
- [{auto_merge_checkbox}] Auto-merge after CI
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
    chunk_id = chunk_id or PROJECT.default_gate_chunk
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
    commands = gate_commands(
        python=python,
        focused_targets=focused_targets,
        test_command_tail=PROJECT.test_command_tail,
        test_flags=PROJECT.test_flags,
        lint_command_tail=PROJECT.lint_command_tail,
    )
    focused = _run_and_summarize(commands["focused"], root)
    full_pytest = _run_and_summarize(commands["full"], root)
    ruff = _run_and_summarize(commands["lint"], root)
    smoke = _import_smoke(config.get("smoke_imports", list(PROJECT.default_smoke_imports)), root)
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


def command_sync(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    changed = sync_progress(root)
    print(f"{PROJECT.progress_filename} {'synced' if changed else 'already synced'}")
    return 0


def command_context(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    brief = build_chunk_context(root, args.chunk)
    if args.json:
        print(json.dumps(engine.chunk_brief_to_dict(brief), indent=2))
    else:
        print(engine.render_chunk_brief(brief), end="")
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
        auto_merge=args.auto_merge,
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


def _maybe_delete_branch(remote: str, token: str, ref: str, *, delete: bool) -> None:
    """Idempotently delete a merged PR's branch; an already-gone branch is success."""
    if not (delete and ref):
        return
    if delete_remote_branch_via_api(remote, token, ref):
        print(f"deleted branch: {ref}")
    else:
        print(f"branch already absent: {ref}")


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

    wait_seconds = clamp_wait_seconds(args.wait)
    if wait_seconds != args.wait:
        print(f"note: --wait {args.wait} clamped to {wait_seconds}s (max {MAX_WAIT_SECONDS})")
    readiness = wait_for_pr_merge_readiness(
        remote=remote,
        token=credential.token,
        pr_number=args.pr,
        wait_seconds=wait_seconds,
        poll_seconds=args.poll,
        ignored_checks=set(getattr(args, "ignore_check", [])),
    )
    if readiness.already_merged:
        print(f"already merged: {readiness.head_sha[:7]}")
        _maybe_delete_branch(
            remote, credential.token, readiness.head_ref, delete=args.delete_branch
        )
        return 0
    if not readiness.ready:
        print("PR is not safe to auto-merge yet (poll with `jh.py pr-status`):")
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
    _maybe_delete_branch(
        remote, credential.token, readiness.head_ref, delete=args.delete_branch
    )
    return 0


def command_ci_auto_merge(args: argparse.Namespace) -> int:
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not event_path.exists() or not token or not repository:
        print("CI auto-merge skipped: missing GitHub Actions event, token, or repository.")
        return 0
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pr_event = event.get("pull_request")
    if not pr_event:
        print("CI auto-merge skipped: event is not a pull_request.")
        return 0
    remote = f"https://github.com/{repository}"
    pr_number = int(pr_event["number"])
    pr = get_pull_request_via_api(remote, token, pr_number)
    if not pr_requests_auto_merge(pr, label=args.label, body_flag=args.body_flag):
        print("CI auto-merge skipped: PR did not opt in.")
        return 0
    readiness = wait_for_pr_merge_readiness(
        remote=remote,
        token=token,
        pr_number=pr_number,
        wait_seconds=clamp_wait_seconds(args.wait),
        poll_seconds=args.poll,
        ignored_checks=set(args.ignore_check),
    )
    if readiness.already_merged:
        print(f"CI auto-merge: PR #{pr_number} already merged ({readiness.head_sha[:7]})")
        _maybe_delete_branch(remote, token, readiness.head_ref, delete=args.delete_branch)
        return 0
    if not readiness.ready:
        print("CI auto-merge blocked:")
        for issue in readiness.issues:
            print(f"- {issue}")
        return 1
    merge = merge_pr_via_api(
        remote=remote,
        token=token,
        pr_number=pr_number,
        head_sha=readiness.head_sha,
        method=args.method,
    )
    print(f"CI auto-merged PR #{pr_number}: {merge['sha'][:7]}")
    _maybe_delete_branch(remote, token, readiness.head_ref, delete=args.delete_branch)
    return 0


def command_pr_comments(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    credential = resolve_github_token(root)
    remote = _github_remote(root)
    if not credential:
        print("Missing GitHub credential; run auth-login or set JH_GITHUB_TOKEN.")
        return 1
    if not remote:
        print("Missing GitHub origin remote.")
        return 1
    comments = get_pr_comments_via_api(remote, credential.token, args.pr)
    if getattr(args, "json", False):
        print(json.dumps({"pr": args.pr, "comments": comments}, indent=2))
    else:
        print(engine.render_pr_comments(comments))
    return 0


def command_pr_status(args: argparse.Namespace) -> int:
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
        wait_seconds=0,
        poll_seconds=0,
        ignored_checks=set(getattr(args, "ignore_check", [])),
    )
    if readiness.already_merged:
        state = "merged"
    elif readiness.ready:
        state = "ready"
    else:
        state = "pending"
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "pr": args.pr,
                    "state": state,
                    "merged": readiness.already_merged,
                    "ready": readiness.ready,
                    "head_sha": readiness.head_sha,
                    "issues": list(readiness.issues),
                }
            )
        )
    else:
        print(f"PR #{args.pr}: {state}")
        for issue in readiness.issues:
            print(f"- {issue}")
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
    print(PROJECT.guide_text)
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
        if sync_progress(root):
            print(f"synced {PROJECT.progress_filename}")
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
    ignored_checks: set[str] | None = None,
    sleep=time.sleep,
) -> PullRequestReadiness:
    deadline = time.monotonic() + wait_seconds
    last_readiness = PullRequestReadiness(False, ("PR readiness not checked",), "", "")
    while True:
        pr = get_pull_request_via_api(remote, token, pr_number)
        if pr_already_merged(pr):
            head = pr.get("head", {})
            return PullRequestReadiness(
                False,
                ("PR already merged",),
                head.get("sha", ""),
                head.get("ref", ""),
                already_merged=True,
            )
        checks = get_check_runs_via_api(remote, token, pr["head"]["sha"])
        statuses = get_statuses_via_api(remote, token, pr["head"]["sha"])
        readiness = evaluate_pr_merge_readiness(
            pr, checks, statuses, ignored_checks=ignored_checks
        )
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


def get_pr_comments_via_api(remote: str, token: str, pr_number: int) -> list[dict[str, Any]]:
    issue = _github_api_json(remote, token, f"/issues/{pr_number}/comments")
    review = _github_api_json(remote, token, f"/pulls/{pr_number}/comments")
    comments: list[dict[str, Any]] = []
    for item in issue if isinstance(issue, list) else []:
        comments.append({
            "kind": "issue",
            "user": (item.get("user") or {}).get("login"),
            "body": item.get("body", ""),
            "path": None,
        })
    for item in review if isinstance(review, list) else []:
        comments.append({
            "kind": "review",
            "user": (item.get("user") or {}).get("login"),
            "body": item.get("body", ""),
            "path": item.get("path"),
        })
    return comments


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
        prog=PROJECT.cli_prog, description=PROJECT.cli_description
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

    sync = sub.add_parser("sync")
    sync.set_defaults(func=command_sync)

    context = sub.add_parser("context")
    context.add_argument("chunk")
    context.add_argument("--json", action="store_true")
    context.set_defaults(func=command_context)

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
    gate.add_argument("chunk", nargs="?", default=PROJECT.default_gate_chunk)
    gate.add_argument("--ci", action="store_true")
    gate.set_defaults(func=command_gate)

    pr_ready = sub.add_parser("pr-ready")
    pr_ready.add_argument("chunk")
    pr_ready.add_argument("--slug", default="workflow automation harness")
    pr_ready.add_argument("--summary", default="Adds deterministic workflow automation.")
    pr_ready.add_argument("--design-note", default="Pure workflow checks with a thin CLI shell.")
    pr_ready.add_argument("--risk-read", default="Low: tooling-only chunk.")
    pr_ready.add_argument("--auto-merge", action="store_true")
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
    merge_pr.add_argument("--ignore-check", action="append", default=[])
    merge_pr.add_argument("--delete-branch", action="store_true")
    merge_pr.add_argument("--dry-run", action="store_true")
    merge_pr.set_defaults(func=command_merge_pr)

    pr_status = sub.add_parser("pr-status")
    pr_status.add_argument("pr", type=int)
    pr_status.add_argument("--json", action="store_true")
    pr_status.add_argument("--ignore-check", action="append", default=[])
    pr_status.set_defaults(func=command_pr_status)

    pr_comments = sub.add_parser("pr-comments")
    pr_comments.add_argument("pr", type=int)
    pr_comments.add_argument("--json", action="store_true")
    pr_comments.set_defaults(func=command_pr_comments)

    ci_auto_merge = sub.add_parser("ci-auto-merge")
    ci_auto_merge.add_argument("--label", default="auto-merge")
    ci_auto_merge.add_argument("--body-flag", default="Auto-merge after CI")
    ci_auto_merge.add_argument("--wait", type=int, default=300)
    ci_auto_merge.add_argument("--poll", type=int, default=10)
    ci_auto_merge.add_argument("--method", choices=["merge", "squash", "rebase"], default="merge")
    ci_auto_merge.add_argument("--ignore-check", action="append", default=["auto-merge"])
    ci_auto_merge.add_argument("--delete-branch", action="store_true")
    ci_auto_merge.set_defaults(func=command_ci_auto_merge)

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
