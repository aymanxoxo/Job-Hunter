# PROGRESS — JobHunter live tracker

> Read this first. With [`Documents/JobHunter_DEV_PLAN_v1.0.md`](Documents/JobHunter_DEV_PLAN_v1.0.md)
> and `git log`, this file is the whole project state. Update it **in the same commit** as each chunk,
> on that chunk's `chunk/C-XXX` branch (merged to `main` via a reviewed PR — ADR-015).
> Each chunk only moves to `done` after passing the Definition-of-Done gate (plan §3.1) and validation
> sequence (plan §3.2).

## Orientation

<!-- jh:orientation:start -->
- **Phase:** Phase 1 - Foundation. **Next gate:** M-03 (chunk C-029).
- **Last done:** **C-048** - Deterministic PR review-comment fetch (`e5ba1d8`). Prior done: **C-047** - One-command chunk context brief (`6805055`); **C-046** - Generated PROGRESS orientation + sync (`75e1ae2`).
- **Next ready:** **C-016** - Google OAuth device flow (risk-flagged; design sign-off required); **C-020** - Indeed connector (risk-flagged; design sign-off required); **C-021** - LinkedIn connector (risk-flagged; design sign-off required); **C-022** - Pure pipeline transforms; **C-023** - Progress event emitter; **C-024** - Output exporter; **C-030** - OpenRouter provider; **C-038** - Authoring docs — **M-06 gate**; **C-049** - Plugin-load fail-graceful + raw read-only.
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
| C-047 | One-command chunk context brief | Tooling | C-045 | done | 6805055 |
| C-048 | Deterministic PR review-comment fetch | Tooling | C-043 | done | e5ba1d8 |
| C-049 | Plugin-load fail-graceful + raw read-only | Hardening | C-004, C-009 | todo | — |
| C-050 | Retire walking skeleton + re-point CLI | Cleanup | C-024, C-025, C-026 | todo | — |
| C-007 | BaseProfileInput ABC + text parser | Contracts | C-004 | done | ff83ca3 |
| C-008 | Auth strategy resolver | Contracts | C-002, C-003 | done | 7d96047 |
| C-009 | Plugin discovery | Contracts | C-005, C-006, C-007 | done | c1e32ad |
| C-010 | Prompt builders (pure) | AI engine | C-004 | done | df227d5 |
| C-011 | Response parsers (pure) | AI engine | C-004 | done | 1532e86 |
| C-012 | Job field-stripper (pure) | AI engine | C-004 | done | d5565b6 |
| C-013 | Batching util (pure) | AI engine | C-004 | done | 7bef68d |
| C-014 | AI engine facade | AI engine | C-006, C-010, C-011, C-012, C-013 | done | a9138e2 |
| C-015 | Ollama provider | Providers | C-006, C-014 | done | 70c71f6 |
| C-016 | Google OAuth device flow | Providers | C-002, C-008 | todo | — |
| C-017 | Gemini provider | Providers | C-006, C-008, C-016 | todo | — |
| C-018 | Mock connector + fixtures | Connectors | C-005 | done | 5acca79 |
| C-019 | Session store | Connectors | C-002 | done | 9fb5ce0 |
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

- 2026-06-19 - **C-049** (urgent, todo) + **C-050** (todo) added from the C-019 code-review checkpoint: C-049 hardens plugin discovery to be fail-graceful (per-file import errors warn+skip) and makes `Job.raw` read-only; C-050 retires the walking-skeleton stubs and re-points the CLI once the real runner/output/CLI land (deps C-024/C-025/C-026).
- 2026-06-19 - **C-019** Session store on `chunk/C-019-session-store`: `core.auth.SessionStore` Fernet-encrypts Playwright storage-state, derives a machine key via PBKDF2HMAC through keyring, save/load/exists/delete, rejects unsafe names. Merged `9fb5ce0` (PR #39).
- 2026-06-19 - **C-018** Mock connector + fixtures on `chunk/C-018-mock-connector`: `core.connectors.MockConnector` loads deterministic jobs from `fixtures/jobs.json`, enforces `source="mock"`, case-insensitive keyword filter. Merged `5acca79` (PR #38).
- 2026-06-19 - **C-015** Ollama provider on `chunk/C-015-ollama-provider`: `core.ai_providers.OllamaProvider` calls local Ollama `/api/generate`, delegates to `AIEngine`; tests fake HTTP via `httpx.MockTransport`. Merged `70c71f6` (PR #37).
- 2026-06-19 - **C-014** AI engine facade on `chunk/C-014-ai-engine-facade`: `core.ai_engine.AIEngine` wraps an injected async provider, builds/batches prompts, parses provider JSON, returns scored `Job` copies without mutating inputs. Merged `a9138e2` (PR #36).
- 2026-06-19 - **C-013** Batching util `core.ai_engine.batching.batch_items` merged `7bef68d` (PR #35).
- 2026-06-19 - **C-012** Job field-stripper `core.ai_engine.scrub` merged `d5565b6` (PR #34).
- 2026-06-19 - **C-011** Response parsers `core.ai_engine.parsing` merged `1532e86` (PR #33).
- 2026-06-19 - **C-010** Prompt builders `core.ai_engine.prompts` merged `df227d5` (PR #32).
- 2026-06-19 - **C-008** Auth strategy resolver `core.auth.auth_strategy.resolve_auth` (ordered methods, injected oauth/session, env api-key) merged `7d96047` (PR #31).
- 2026-06-19 - **C-009** Plugin discovery `core.runner.discover_plugins` (importlib drop-in loading) merged `c1e32ad` (PR #30).
- 2026-06-19 - **C-048** Deterministic PR review-comment fetch on `chunk/C-048-pr-comments`: `jh.py pr-comments <#>` fetches review threads + issue comments, renders or `--json`, degrades without API access. Merged `e5ba1d8` (PR #29).
- 2026-06-19 - **C-047** One-command chunk context brief: `jh.py context C-XXX` assembles registry metadata, SDD excerpts, ADR titles, AGENTS pointers, gate evidence, JSON. Merged `6805055`.
- 2026-06-19 - **C-046** Generated PROGRESS orientation + sync: `jh.py sync` regenerates the sentinel orientation, backfills merge hashes; `doctor` fails stale orientation. Merged `75e1ae2` (ADR-026).
- 2026-06-19 — **C-044** Decouple engine from project business: `tools/jh.py` split into `jh_engine.py` + `jh_project.py` + thin shell; doctor engine-purity check + fixture-adapter test. Merged `655c483` (ADR-025).
- 2026-06-19 — **C-045** Chunk registry SSOT: `tools/chunks.json` + `check_registry_consistency`. Merged `d0c007e` (ADR-024).
- 2026-06-19 — **C-043** Async-by-default + idempotent long-running waits; `pr-status` poll. Merged `853a6bb` (ADR-023).
- 2026-06-18 — **C-007** BaseProfileInput ABC + text parser. Merged `ff83ca3` (PR #22).
- 2026-06-18 — **C-039** Walking skeleton (stub provider/connector + JSON export + `jobhunter run`). Merged `a722329` (PR #20).
- 2026-06-18 — **C-042** CI-native opt-in auto-merge. Merged `5e1ef5a` (PR #18).
- 2026-06-18 — **C-041** CI-gated auto-merge command. Merged `6886786` (PR #16).
- 2026-06-18 — **C-040** Workflow automation harness. Merged `796a012` (PR #14).
- 2026-06-18 — **C-006** BaseAIProvider ABC. Merged `27dd173` (PR #12).
- 2026-06-18 — **C-005** BaseConnector ABC. Merged `a796edd` (PR #10).
- 2026-06-18 — **Hardening** config `extra=forbid`, enum, tuple containers (ADR-018). Merged `e758131` (PR #8).
- 2026-06-17 — **C-003** config models + loader. Merged `b3e45f9`, tag `C-003`.
- 2026-06-17 — **C-004** data models (frozen Job + SearchCriteria). Merged `d86d7aa`, tag `C-004`.
- 2026-06-17 — **C-002** logging & trace core (JSON, stderr-only, redaction). Merged `5f1ae5f`, tag `C-002`.
- 2026-06-17 — **C-001** scaffold. Merged `808d1ca`, tag `C-001`.
- 2026-06-17 — C-000 done: git initialized, initial snapshot `5cf9ee3`; added `Documents/DECISIONS.md`.
- 2026-06-17 — Plan v1.0 authored; ledger seeded with 38 chunks (C-001…C-038).
