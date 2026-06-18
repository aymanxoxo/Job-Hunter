# HANDOFF — start here if you're a new AI taking over JobHunter

You're continuing development of **JobHunter** — a local, plugin-based AI job-search aggregator (Python
core + CLI now; Tauri + Vue desktop later). Built test-first, one small chunk at a time. This file gets
you productive fast; the repo is the source of truth.

## Read first, in order
1. `AGENTS.md` (root) — the map: project, conventions, doc layers, dev workflow.
2. `PROGRESS.md` — the live tracker. Orientation block = last-done / next-ready / blocked; the ledger is
   the full chunk plan (C-001…C-039) with statuses + merge hashes. **This is current state.**
3. `Documents/JobHunter_DEV_PLAN_v1.0.md` — the chunk model, per-chunk vertical protocol (§3.3), the
   Definition-of-Done gate (§3.1), commit + ledger conventions (§7–8), the live-progress UI spec (§9),
   and the full chunk specs (§10).
4. `Documents/DECISIONS.md` — ADRs (the *why*; don't relitigate settled decisions).
5. `Documents/JobHunter_SDD_v1.1.md` (deep spec) + each module's `AGENTS.md` as you touch it.

## How to work — one chunk at a time, test-first
- Start with the deterministic harness: `python tools/jh.py bootstrap`, then `python tools/jh.py status`
  and `python tools/jh.py next`. Use the docs for judgment and context, but let the harness do the
  mechanical state discovery whenever possible.
- Before starting a chunk or code change, ask the user whether the resulting PR should be auto-merged
  after green CI or held for manual review. Encode the answer in the PR body checkbox
  `Auto-merge after CI` or with the `auto-merge` label.
- Pick the next ready chunk from `PROGRESS.md` (ready = all `Depends on` are `done`); confirm with the
  user before starting.
- Vertical protocol per chunk: **design → failing tests (red) → implement (green) → refactor + full
  `pytest`/`ruff` gate → verify → land**. Risk-flagged chunks (C-008, C-016/017, C-020/021, C-025,
  C-031, C-033) pause for the user's design sign-off before code.
- Style: functional core / imperative shell — pure single-job functions, effects in thin adapters,
  immutable models (frozen + tuples), structured logging via `core.logging`, **stderr only** (stdout is
  the sidecar IPC channel).
- Each chunk = **one commit** on a `chunk/C-XXX-slug` branch: `<type>(<scope>): <summary>  [C-XXX]`;
  update the `PROGRESS` ledger row to `done` in that commit; add tech/business docs where warranted
  (ADR-017: module `AGENTS.md` + `Documents/PRODUCT_NOTES.md`).
- PR descriptions: generate them with `python tools/jh.py pr-ready C-XXX` when possible; every handoff
  stays short and human-readable (design note + red→green test evidence + full gate evidence + a
  one-line risk read).
  After the user merges a chunk's PR: pull `main`, tag the merge commit `C-XXX`, delete the branch.

## Environment (you run locally now)
Git/GitHub capability can differ by AI runtime. Every agent should take the workflow as far as its
available access allows, while the user remains the review/merge gate:

1. If PR creation is available, create the GitHub PR directly and give the user the PR URL.
2. If PR creation is unavailable but branch push works, push the branch and give the user the GitHub
   compare/new-PR URL.
3. If branch push is unavailable, provide the diff/patch plus exact PR title and description for manual
   creation.

Every PR or manual PR handoff must include a clear title (with the chunk ID when applicable), a
human-readable description, the Design note, red→green test evidence, full gate evidence, and a one-line
risk read. Prefer `python tools/jh.py auth-status` and `python tools/jh.py create-pr C-XXX`; the harness
uses authenticated `gh`, `auth-login` OAuth device flow, `JH_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN`, or
Git Credential Manager before it falls back to the compare URL or patch handoff. Validate with
`python tools/jh.py gate C-XXX`, which runs the deterministic doctor, focused tests, full pytest, ruff,
and import smoke checks.
- Auto-merge is allowed only when the user has explicitly allowed it for the PR class. Use
  `python tools/jh.py merge-pr <PR_NUMBER> --wait 600`; it refuses draft, unmergeable, pending, failed,
  or missing-CI PRs.
- CI also runs the same policy natively: when a PR has the `auto-merge` label or checked
  `Auto-merge after CI` PR-body box, the workflow merges it after all validation jobs pass.

## FIRST TASK — continue after C-040
C-006 (BaseAIProvider ABC) is merged at `27dd173`. C-040 adds the deterministic workflow harness. If
this branch is merged, tag the merge commit `C-040`, delete `chunk/C-040-workflow-automation-harness`,
then run `python tools/jh.py status` and pick up the next ready chunk from `PROGRESS.md`.

## Where we are
Foundation (C-001–C-006), a config/model hardening fix, and the C-040 workflow harness are complete or
in review. Next ready: C-007 (BaseProfileInput + text parser), C-008 (auth resolver — risk-flagged),
C-018 (mock connector), C-039 (walking skeleton).
