# PROGRESS — JobHunter live tracker

> Read this first. With [`Documents/JobHunter_DEV_PLAN_v1.0.md`](Documents/JobHunter_DEV_PLAN_v1.0.md)
> and `git log`, this file is the whole project state. Update it **in the same commit** as each chunk,
> on that chunk's `chunk/C-XXX` branch (merged to `main` via a reviewed PR — ADR-015).
> Each chunk only moves to `done` after passing the Definition-of-Done gate (plan §3.1) and validation
> sequence (plan §3.2).

## Orientation

- **Phase:** Phase 1 — Foundation. **Next gate:** M-03 (chunk C-029).
- **Last done:** **C-040** — Workflow automation harness (bootstrap/status/next/start/doctor/gate/PR helpers; full gate green). Prior: **C-006** BaseAIProvider merged `27dd173`.
- **Next ready:** **C-007** (profile-input ABC), **C-008** (auth resolver — risk-flagged), **C-018** (mock connector), **C-039** (walking skeleton).
- **Blocked:** none.
- **Notes:** Dev loop runs via the GitHub remote (the mount can't hold `.git`): the AI works in a
  sandbox clone, pushes one `chunk/C-XXX` branch per chunk with a risk read; the user reviews + merges the
  PR; the AI tags `C-XXX` + deletes the branch. See [ADR-014/015/016](Documents/DECISIONS.md).
- **Protocol:** each chunk runs the six-step vertical (design→test→impl→gate→verify→land, plan §3.3);
  risky chunks get a Design sign-off first. A walking skeleton (C-039) runs right after C-001.

## Status legend

`todo` · `in-progress` · `done` · `blocked` — readiness = all *Depends on* chunks are `done`.

## Ledger

| ID | Title | Stage | Depends on | Status | Merge |
|----|-------|-------|-----------|--------|--------|
| C-000 | Repo init + initial project snapshot | Bootstrap | — | done | 5cf9ee3 |
| C-001 | Repo scaffold + tooling | Foundation | C-000 | done | 808d1ca |
| C-039 | Walking skeleton (stub end-to-end) | Skeleton | C-001 | todo | — |
| C-002 | Logging & trace core | Foundation | C-001 | done | 5f1ae5f |
| C-003 | Config models + loader | Foundation | C-001, C-002 | done | b3e45f9 |
| C-004 | Data models (Job, SearchCriteria) | Foundation | C-001 | done | d86d7aa |
| C-005 | BaseConnector ABC | Contracts | C-004 | done | a796edd |
| C-006 | BaseAIProvider ABC | Contracts | C-004 | done | 27dd173 |
| C-040 | Workflow automation harness | Tooling | C-006 | done | 796a012 |
| C-007 | BaseProfileInput ABC + text parser | Contracts | C-004 | todo | — |
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
