"""JobHunter project adapter — the only place JobHunter-specific knowledge lives.

The generic engine (tools/jh_engine.py) is parameterized by a ProjectConfig. To reuse
the workflow for another repo (template / skill / agent / package), supply a different
ProjectConfig; the engine and CLI shell stay unchanged (ADR-025).
"""

from __future__ import annotations

from dataclasses import dataclass

GUIDE_TEXT = """JobHunter AI workflow quick guide

1. python tools/jh.py bootstrap
2. python tools/jh.py status
3. python tools/jh.py next
4. python tools/jh.py start C-XXX --branch chunk/C-XXX-slug
5. Write red tests, implement, then run: python tools/jh.py gate C-XXX
6. Commit once with: <type>(<scope>): <summary>  [C-XXX]
7. python tools/jh.py pr-ready C-XXX
8. python tools/jh.py auth-status
9. python tools/jh.py create-pr C-XXX
10. Merge async (do not block): python tools/jh.py merge-pr <PR_NUMBER>
    then poll: python tools/jh.py pr-status <PR_NUMBER>
11. After merge: python tools/jh.py after-merge C-XXX --branch chunk/C-XXX-slug

Credential options for direct PR creation:
- gh CLI already authenticated, or
- python tools/jh.py auth-login with a GitHub OAuth app client ID, or
- JH_GITHUB_TOKEN / GH_TOKEN / GITHUB_TOKEN with Pull requests: read/write, or
- Git Credential Manager storing a GitHub token usable by the GitHub API.

The harness never prints token values and writes generated evidence under output/agent/.
"""


@dataclass(frozen=True)
class ProjectConfig:
    """Everything project-specific the generic engine/shell needs, in one place."""

    name: str
    progress_filename: str
    registry_relpath: str
    dev_plan_relpath: str
    pr_template_relpath: str
    source_check_dir: str
    chunk_id_regex: str
    branch_regex: str
    default_risk_flagged: frozenset[str]
    default_smoke_imports: tuple[str, ...]
    plugin_boundaries: tuple[tuple[str, str], ...]
    test_command_tail: tuple[str, ...]
    test_flags: tuple[str, ...]
    lint_command_tail: tuple[str, ...]
    default_gate_chunk: str
    cli_prog: str
    cli_description: str
    guide_text: str
    forbidden_engine_identifiers: tuple[str, ...]


JOBHUNTER = ProjectConfig(
    name="JobHunter",
    progress_filename="PROGRESS.md",
    registry_relpath="tools/chunks.json",
    dev_plan_relpath="Documents/JobHunter_DEV_PLAN_v1.0.md",
    pr_template_relpath=".github/PULL_REQUEST_TEMPLATE.md",
    source_check_dir="core",
    chunk_id_regex=r"C-\d{3}",
    branch_regex=r"chunk/C-\d{3}-[a-z0-9][a-z0-9-]*",
    default_risk_flagged=frozenset(
        {"C-008", "C-016", "C-017", "C-020", "C-021", "C-025", "C-031", "C-033"}
    ),
    default_smoke_imports=("core",),
    plugin_boundaries=(
        ("core/connectors", "ai_providers"),
        ("connectors", "ai_providers"),
        ("core/ai_providers", "connectors"),
        ("ai_providers", "connectors"),
    ),
    test_command_tail=("-m", "pytest"),
    test_flags=("-q", "--asyncio-mode=auto"),
    lint_command_tail=("-m", "ruff", "check", "."),
    default_gate_chunk="C-040",
    cli_prog="jh",
    cli_description="JobHunter deterministic workflow harness",
    guide_text=GUIDE_TEXT,
    forbidden_engine_identifiers=(
        "JobHunter",
        "PROGRESS.md",
        "chunks.json",
        "JobHunter_DEV_PLAN",
        "core/connectors",
        "core/ai_providers",
        "config.yaml",
        "C-008",
    ),
)
