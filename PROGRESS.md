# PROGRESS — JobHunter live tracker

> Read this first. With [`Documents/JobHunter_DEV_PLAN_v1.0.md`](Documents/JobHunter_DEV_PLAN_v1.0.md)
> and `git log`, this file is the whole project state. Update it **in the same commit** as each chunk.
> Each chunk only moves to `done` after passing the Definition-of-Done gate (plan §3.1) and validation
> sequence (plan §3.2).

## Orientation

- **Phase:** Phase 1 — Foundation. **Next gate:** M-03 (chunk C-029).
- **Last done:** — (no implementation chunks yet; planning + docs complete)
- **Next ready:** **C-001** (Repo scaffold + tooling) — no dependencies.
- **Blocked:** none.
- **Notes:** Git to be initialised locally by the user before C-001's first commit (see chat / SDD §13.4).

## Status legend

`todo` · `in-progress` · `done` · `blocked` — readiness = all *Depends on* chunks are `done`.

## Ledger

| ID | Title | Stage | Depends on | Status | Commit |
|----|-------|-------|-----------|--------|--------|
| C-001 | Repo scaffold + tooling | Foundation | — | todo | — |
| C-002 | Logging & trace core | Foundation | C-001 | todo | — |
| C-003 | Config models + loader | Foundation | C-001, C-002 | todo | — |
| C-004 | Data models (Job, SearchCriteria) | Foundation | C-001 | todo | — |
| C-005 | BaseConnector ABC | Contracts | C-004 | todo | — |
| C-006 | BaseAIProvider ABC | Contracts | C-004 | todo | — |
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

- 2026-06-17 — Plan v1.0 authored; ledger seeded with 38 chunks (C-001…C-038). No code yet.
