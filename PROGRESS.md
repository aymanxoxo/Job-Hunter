# PROGRESS — JobHunter live tracker

> Read this first. With [`Documents/JobHunter_DEV_PLAN_v1.0.md`](Documents/JobHunter_DEV_PLAN_v1.0.md)
> and `git log`, this file is the whole project state. Update it **in the same commit** as each chunk,
> on that chunk's `chunk/C-XXX` branch (merged to `main` via a reviewed PR — ADR-015).
> Each chunk only moves to `done` after passing the Definition-of-Done gate (plan §3.1) and validation
> sequence (plan §3.2).

## Orientation

<!-- jh:orientation:start -->
- **Phase:** Phase 1 - Foundation. **Next gate:** M-03 (chunk C-029).
- **Last done:** **C-047** - One-command chunk context brief (merge pending). Prior done: **C-046** - Generated PROGRESS orientation + sync (`75e1ae2`); **C-044** - Decouple engine from project business (`655c483`).
- **Next ready:** **C-008** - Auth strategy resolver (risk-flagged; design sign-off required); **C-009** - Plugin discovery; **C-010** - Prompt builders (pure); **C-011** - Response parsers (pure); **C-012** - Job field-stripper (pure); **C-013** - Batching util (pure); **C-018** - Mock connector + fixtures; **C-019** - Session store; **C-020** - Indeed connector (risk-flagged; design sign-off required); **C-022** - Pure pipeline transforms; **C-023** - Progress event emitter; **C-024** - Output exporter; **C-038** - Authoring docs — **M-06 gate**.
- **Blocked:** none.
- **Notes:** Dev loop runs through short-lived GitHub PR branches; the user reviews and merges. See [ADR-014/015/016](Documents/DECISIONS.md).
- **Protocol:** each chunk runs design -> test -> impl -> gate -> verify -> land (plan section 3.3); risky chunks pause for Design sign-off.
<!-- jh:orientation:end -->

## Status legend

`todo` · `in-progress` · `done` · `blocked` — readiness = all *Depends on* chunks are `done`.

## Ledger

| ID | Title | Stage | Depends on | Status | Merge |
|----|-------|-------|-----------|--------|--------|
| C-000 | Repo init + initial project snapshot | Bootstrap | — | done | 5cf9ee3 |
| C-001 | Repo scaffold + tooling | Foundation | C-000 | done | 808d1ca |
| C-039 | Walking skeleton (stub end-to-end) | Skeleton | C-001 | done | a722329 |
| C-002 | Logging & trace core | Foundation | C-001 | done | 5f1ae5f |
| C-003 | Config models + loader | Foundation | C-001, C-002 | done | b3e45f9 |
| C-004 | Data models (Job, SearchCriteria) | Foundation | C-001 | done | d86d7aa |
| C-005 | BaseConnector ABC | Contracts | C-004 | done | a796edd |
| C-006 | BaseAIProvider ABC | Contracts | C-004 | done | 27dd173 |
| C-040 | Workflow automation harness | Tooling | C-006 | done | 796a012 |
| C-041 | CI-gated auto-merge command | Tooling | C-040 | done | 6886786 |
| C-042 | CI-native opt-in auto-merge | Tooling | C-041 | done | 5e1ef5a |
| C-043 | Async/idempotent long-running waits | Tooling | C-042 | done | 853a6bb |
| C-045 | Chunk registry single source of truth | Tooling | C-040 | done | d0c007e |
| C-044 | Decouple engine from project business | Tooling | C-045 | done | 655c483 |
| C-046 | Generated PROGRESS orientation + sync | Tooling | C-044 | done | 75e1ae2 |
| C-047 | One-command chunk context brief | Tooling | C-045 | done | (PR) |
| C-007 | BaseProfileInput ABC + text parser | Contracts | C-004 | done | ff83ca3 |
| C-008 | Auth strategy resolver | Contracts | C-002, C-003 | todo | — |
| C-009 | Plugin discovery | Contracts | C-005, C-006, C-007 | todo | — |
| C-010 | Prompt builders (pure) | AI engine | C-004 | todo | — |
| C-011 | Response parsers (pure) | AI engine | C-004 | todo | — |
| C-012 | Job field-stripper (pure) | AI engine | C-004 | todo | — |
| C-013 | Batching util (pure) | AI engine | C-004 | todo | — |
| C-014 | AI engine facade | AI engine | C-006, C-010, C-011, C-012, C-013 | todo | — |
| C-015 | Ollama provider | Providers | C-006, C-014 | todo | — |
| C-016 | Google OAuth device flow | Providers | C-002, C-008 | todo | — |
| C-017 | Gemini provider | Providers | C-006, C-008, C-016 | todo | — |
| C-018 | Mock connector + fixtures | Connectors | C-005 | todo | — |
| C-019 | Session store | Connectors | C-002 | todo | — |
| C-020 | Indeed connector | Connectors | C-005 | todo | — |
| C-021 | LinkedIn connector | Connectors | C-005, C-019 | todo | — |
| C-022 | Pure pipeline transforms | Pipeline | C-004 | todo | — |
| C-023 | Progress event emitter | Pipeline | C-002 | todo | — |
| C-024 | Output exporter | Pipeline | C-004 | todo | — |
| C-025 | Runner orchestrator | Pipeline | C-009, C-014, C-022, C-023, C-024, ≥1 provider, ≥1 connector | todo | — |
| C-026 | CLI skeleton + run + Rich render | CLI | C-025 | todo | — |
| C-027 | CLI auth commands | CLI | C-016, C-017, C-019, C-021 | todo | — |
| C-028 | CLI config/list/export commands | CLI | C-003, C-009, C-024 | todo | — |
| C-029 | E2E CLI test — **M-03 gate** | CLI | C-026, C-018, C-015 | todo | — |
| C-030 | OpenRouter provider | Phase 2 | C-006, C-014 | todo | — |
| C-031 | Tauri shell + sidecar + IPC | Phase 2 | C-026, C-023 | todo | — |
| C-032 | Vue app scaffold | Phase 2 | C-031 | todo | — |
| C-033 | Live Pipeline Progress UX | Phase 2 | C-032, C-023 | todo | — |
| C-034 | Criteria View | Phase 2 | C-032 | todo | — |
| C-035 | Results View | Phase 2 | C-032 | todo | — |
| C-036 | Settings View | Phase 2 | C-032, C-003 | todo | — |
| C-037 | Windows installer | Phase 2 | C-033, C-034, C-035, C-036, C-030 | todo | — |
| C-038 | Authoring docs — **M-06 gate** | Phase 2 | C-005, C-006, C-007 | todo | — |

## Changelog (newest first)

- 2026-06-19 - **C-047** One-command chunk context brief on `chunk/C-047-context-command`: `jh.py context C-XXX` assembles registry metadata, dev-plan-sourced files/SDD anchors, SDD excerpts, ADR titles, module AGENTS pointers, optional gate evidence, and JSON output. Gate green (`pytest`, `ruff`, import smoke). (PR pending.)
- 2026-06-19 - **C-046** Generated PROGRESS orientation + sync on `chunk/C-046-progress-sync`: `jh.py sync` regenerates the sentinel-protected PROGRESS orientation from the chunk graph, backfills done-chunk merge placeholders from git merge commits, and is invoked by `after-merge`; `doctor` now fails stale generated orientation. Added pure engine orientation helpers plus shell sync/backfill tests. 66 focused harness tests green; full gate `python tools/jh.py gate C-046` all-green (120/120 pytest, ruff clean, doctor PASS). (PR pending.) (ADR-026.)
- 2026-06-19 — **C-044** Decouple engine from project business on `chunk/C-044-decouple-engine`: split `tools/jh.py` into `tools/jh_engine.py` (generic, project-agnostic engine — value types + pure planning/eval logic, no project identifiers) + `tools/jh_project.py` (the `ProjectConfig` adapter; `JOBHUNTER` holds every project-specific value) + `jh.py` (thin CLI shell wiring adapter into engine, re-exporting names so the public surface is unchanged). New `doctor` engine-purity check + a fixture-adapter test driving the engine with a non-JobHunter config prove the decoupling. Also backfilled the C-045 merge hash `d0c007e`. 4 tests added, 114/114 green; ruff clean; doctor PASS; gate all-green. (PR pending.) (ADR-025.)
- 2026-06-19 — **C-045** Chunk registry SSOT on `chunk/C-045-chunk-registry`: new `tools/chunks.json` holds per-chunk static metadata (stage/deps/risk/tests) + smoke imports and absorbs `jh_config.json`; `load_config` now derives its legacy shape from the registry (callers unchanged); `doctor` gains `check_registry_consistency` (registry vs PROGRESS ledger vs dev-plan §10, expanding dep ranges like `C-010–C-013`). Also backfilled the C-043 merge hash `853a6bb`. 9 tests added, 110/110 green; ruff clean; doctor PASS. (PR pending.) (ADR-024.)
- 2026-06-19 — **C-043** Async-by-default + idempotent long-running waits on `chunk/C-043-async-waits`: `wait_for_pr_merge_readiness` short-circuits on an already-merged PR (no poll/sleep) and reports `already_merged`; `merge-pr`/`ci-auto-merge` treat that as immediate success and delete the branch idempotently (an already-gone branch is success); `--wait` is hard-capped at 300s (`clamp_wait_seconds`), `merge-pr` defaults to async `--wait 0`; new non-blocking `pr-status <#>` poll. Fixes the reported "agent keeps waiting" hang (ADR-023). 9 focused tests added, 101/101 green; ruff clean. Merged `853a6bb` (PR #24).
- 2026-06-18 — **C-007** BaseProfileInput ABC + text parser on `chunk/C-007-base-profile-input`: `core/profile_inputs/base_profile_input.py` defines async `to_text(source) -> str`, `TextProfileInput` preserves typed text unchanged, and reusable contract tests cover profile input plugins. 6 focused tests green via `tests/test_profile_inputs.py`; full gate via `python tools/jh.py gate C-007 --ci`. Merged `ff83ca3` (PR #22).
- 2026-06-18 — **C-039** Walking skeleton on `chunk/C-039-walking-skeleton`: temporary stub provider + fixture connector + JSON export + `jobhunter run` Click/Rich command prove profile → criteria → search → score → export wiring. 4 focused tests green via `tests/test_walking_skeleton.py`; full gate via `python tools/jh.py gate C-039 --ci`. Merged `a722329` (PR #20).
- 2026-06-18 — **C-042** CI-native opt-in auto-merge on `tools/ci-native-auto-merge`: CI runs `ci-auto-merge` after validations, skips unless `auto-merge` label or checked PR checkbox is present, and docs require the agent to ask for merge policy before starting work. 82/82 tests green; full gate via `python tools/jh.py gate C-040 --ci`. Merged `5e1ef5a` (PR #18).
- 2026-06-18 — **C-041** CI-gated auto-merge command on `tools/ci-gated-auto-merge`: `python tools/jh.py merge-pr <PR_NUMBER>` checks PR state, mergeability, check runs/statuses, and exact head SHA before merging. Full gate via `python tools/jh.py gate C-040`. Merged `6886786` (PR #16).
- 2026-06-18 — **C-040** Workflow automation harness on `chunk/C-040-workflow-automation-harness`: `tools/jh.py` (bootstrap/status/next/start/doctor/gate/pr-ready/create-pr/auth-status/auth-login/guide/after-merge), deterministic doctor checks, GitHub credential/OAuth resolution, CI workflow, and PR evidence generation. 70/70 tests green; full gate via `python tools/jh.py gate C-040`. Merged `796a012` (PR #14).
- 2026-06-18 — **C-006** BaseAIProvider ABC on `chunk/C-006-base-ai-provider`: `core/ai_providers/base_provider.py` (abstract `generate_criteria` + `score_jobs`, ordered `auth_methods`, `initialize`) + reusable provider contract checks; `core/ai_providers/AGENTS.md`. 44/44 tests green, ruff clean. Merged `27dd173` (PR #12).
- 2026-06-18 — **C-005** BaseConnector ABC on `chunk/C-005-base-connector`: `core/connectors/base_connector.py` (abstract `search`, ordered `auth_methods`, `authenticate`) + reusable contract check `tests/contracts/connector_contract.py`; `core/connectors/AGENTS.md`. 35/35 tests green, ruff clean. Merged `a796edd` (PR #10).
- 2026-06-18 — **Hardening** (`fix/config-models-hardening`, review findings): config sub-models now `extra=forbid` (unknown/secret keys fail load), `output.format` enum, `delay_min <= delay_max`; `Job`/`SearchCriteria` containers are tuples (truly immutable). ADR-018. 30/30 tests green, ruff clean. Merged `e758131` (PR #8).
- 2026-06-17 — **C-003** config on `chunk/C-003-config`: `core/config.py` (pydantic models, YAML loader, `KEY__SUBKEY` env overrides, no-secrets validator) + `config.yaml`; first `PRODUCT_NOTES.md` entry. 24/24 tests green, ruff clean. Merged `b3e45f9`, tag `C-003`.
- 2026-06-17 — **C-004** data models on `chunk/C-004-models`: frozen pydantic `Job` + `SearchCriteria` (score 0–100, bounds; `min_score_threshold` default 40 per ADR-006); `core/models/AGENTS.md`. 18/18 tests green, ruff clean. Merged `d86d7aa`, tag `C-004`.
- 2026-06-17 — **C-002** logging & trace core on `chunk/C-002-logging`: `core/logging.py` (JSON logger, stderr-only, `run_id`, secret redaction; pure `format_record`/`redact`); `core/AGENTS.md` added. 10/10 tests green, ruff clean. Merged `5f1ae5f`, tag `C-002`.
- 2026-06-17 — **C-001** scaffold built on `chunk/C-001-scaffold`: package tree (`core/*`, `ui/cli`), user drop-zones, `pyproject.toml` + `requirements*.txt`, ruff + pytest-asyncio config; 3/3 scaffold tests green, ruff clean. Merged `808d1ca`, tag `C-001`.
- 2026-06-17 — Added per-chunk vertical protocol (ADR-016, §3.3), per-chunk dual docs — technical + business (ADR-017, §3.4, `Documents/PRODUCT_NOTES.md`), the PR template, and walking-skeleton chunk C-039; refreshed the workflow Notes.
- 2026-06-17 — C-000 done: git initialized on `main`, initial snapshot committed (`5cf9ee3`). Added
  `Documents/DECISIONS.md` (ADR log). C-001 is the next ready chunk.
- 2026-06-17 — Plan v1.0 authored; ledger seeded with 38 chunks (C-001…C-038). No code yet.
