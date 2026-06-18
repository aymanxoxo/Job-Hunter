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
- PR descriptions: short, human-readable (design note + red→green test evidence + a one-line risk read).
  After the user merges a chunk's PR: pull `main`, tag the merge commit `C-XXX`, delete the branch.

## Environment (you run locally now)
You have direct repo + network access, so — unlike the prior Cowork-sandbox agent — git and GitHub just
work: create branches, push them, and give the user a GitHub compare/PR URL for review. If `gh` is
installed, `gh pr create` / `gh pr view <#> --comments` are fine; otherwise use normal git plus the
browser/API as available. The Cowork-specific notes in ADR-014/015 (sandbox clone, api.github.com
blocked, no PR creation) were environmental and do not apply to you. Validate in the project's Python
(3.11+).

## FIRST TASK — continue from C-006
C-005 (BaseConnector ABC) is merged at `a796edd`; its review finding is fixed and the contract helper
asserts `isinstance(job, Job)`. C-006 adds `BaseAIProvider` and the reusable provider contract checks.
If this branch is merged, tag the merge commit `C-006`, delete `chunk/C-006-base-ai-provider`, then pick
up the next ready chunk from `PROGRESS.md`.

## Where we are
Foundation (C-001–C-005) + a config/model hardening fix are merged. **C-006 (BaseAIProvider ABC)** is the
current routine contract chunk. Next ready after C-006: C-007 (BaseProfileInput + text parser), C-008
(auth resolver — risk-flagged), C-018 (mock connector), C-039 (walking skeleton).
