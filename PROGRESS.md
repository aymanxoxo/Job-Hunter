# PROGRESS — JobHunter live tracker

> Read this first. With [`Documents/JobHunter_DEV_PLAN_v1.0.md`](Documents/JobHunter_DEV_PLAN_v1.0.md)
> and `git log`, this file is the whole project state. Update it **in the same commit** as each chunk,
> on that chunk's `chunk/C-XXX` branch (merged to `main` via a reviewed PR — ADR-015).
> Each chunk only moves to `done` after passing the Definition-of-Done gate (plan §3.1) and validation
> sequence (plan §3.2).

## Orientation

<!-- jh:orientation:start -->
- **Phase:** Phase 1 - Foundation. **Next gate:** M-03 (chunk C-029).
- **Last done:** **C-049** - Plugin-load fail-graceful + raw read-only (`88341c9`). Prior done: **C-048** - Deterministic PR review-comment fetch (`e5ba1d8`); **C-047** - One-command chunk context brief (`6805055`).
- **Next ready:** **C-016** - Google OAuth device flow (risk-flagged; design sign-off required); **C-020** - Indeed connector (risk-flagged; design sign-off required); **C-021** - LinkedIn connector (risk-flagged; design sign-off required); **C-029** - E2E CLI test — **M-03 gate**; **C-030** - OpenRouter provider; **C-031** - Tauri shell + sidecar + IPC (risk-flagged; design sign-off required); **C-038** - Authoring docs — **M-06 gate**; **C-050** - Retire walking skeleton + re-point CLI.
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
| C-049 | Plugin-load fail-graceful + raw read-only | Hardening | C-004, C-009 | done | 88341c9 |
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
| C-022 | Pure pipeline transforms | Pipeline | C-004 | done | 26deae7 |
| C-023 | Progress event emitter | Pipeline | C-002 | done | d5b7e06 |
| C-024 | Output exporter | Pipeline | C-004 | done | 0313037 |
| C-025 | Runner orchestrator | Pipeline | C-009, C-014, C-022, C-023, C-024, ≥1 provider, ≥1 connector | done | e2981a2 |
| C-026 | CLI skeleton + run + Rich render | CLI | C-025 | done | (PR) |
| C-027 | CLI auth commands | CLI | C-016, C-017, C-019, C-021 | todo | — |
| C-028 | CLI config/list/export commands | CLI | C-003, C-009, C-024 | done | 7cfc799 |
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

- 2026-06-20 - **C-026** CLI run + Rich render on `chunk/C-026-cli-run`: `jobhunter run --profile/--profile-file` now drives the real `core.runner` pipeline via `build_runner` and prints a Rich results table; progress events go to stderr so stdout stays the table. Re-points `run` off the C-039 stub (walking_skeleton module retained for C-050); replaced the obsolete skeleton CLI-run test with real-run tests (build_runner injected). 2 focused tests; gate green (235 pytest, ruff, doctor). (PR pending.)
- 2026-06-20 - **C-028** CLI config/list/export commands on `chunk/C-028-cli-config-list-export`: adds `jobhunter config show` with `auth.*` values redacted, `connectors list` and `providers list` backed by built-in + drop-zone plugin discovery, and `export --format csv|json|both` re-exporting the newest configured `results_*.json` through `core.output`. 7 focused CLI tests; gate green (234 pytest, ruff, doctor). Merged `7cfc799` (PR #49).

- 2026-06-20 - **C-025** Runner orchestrator on `chunk/C-025-runner-orchestrator`: `core.runner.Runner` wires the full SDD §5.1 pipeline (profile -> criteria -> parallel fail-graceful search -> merge/dedup -> score -> sort/filter by `min_score_threshold` -> export), emitting a progress event per stage; `build_runner` selects the configured provider + drop-zone connectors via discovery. All collaborators injected (clock/emitter/plugins). 4 focused tests (full flow, per-connector fail-graceful, empty, build_runner selection); gate green (210 pytest, ruff, doctor). Design sign-off in chat. (PR pending.)
- 2026-06-19 - **C-024** Output exporter on `chunk/C-024-output-exporter`: `core.output` writes scored jobs to the configured `output/` dir as timestamped `results_<ts>.csv`/`.json` per `config.output.format` (SDD §5.4); pure `jobs_to_csv`/`jobs_to_json` + injected clock. 7 focused tests; gate green (206 pytest, ruff, doctor). Merged `0313037` (PR #45).
- 2026-06-20 - **C-023** Progress event emitter on `chunk/C-023-progress-event-emitter`: `core.progress` adds a validated `ProgressEvent` schema plus `ProgressEmitter`/`emit_progress_event` for one-JSON-object-per-line stdout protocol events with matching INFO log twins on stderr; event metrics are redacted before emission and invalid stages/states/progress bounds are rejected. Gate green (`216` pytest, `ruff`, import smoke). Merged `d5b7e06` (PR #44).
- 2026-06-19 - **C-022** Pure pipeline transforms on `chunk/C-022-pipeline-transforms`: `core.pipeline` adds pure `merge_results`, `dedup_by_url`, `sort_by_score`, and `filter_below_threshold` helpers for runner steps 8-10; transforms preserve first-seen order where relevant, keep first URL wins for dedupe, treat unscored jobs as zero for sorting, and exclude unscored jobs from threshold filtering. Gate green (`206` pytest, `ruff`, import smoke). Merged `26deae7` (PR #43).
- 2026-06-19 - **C-049** Plugin-load fail-graceful + raw read-only on `chunk/C-049-review-hardening`: `core.runner.discover_plugins` now catches per-file import errors and warn+skips (one broken drop-in plugin no longer aborts discovery of the rest); `Job.raw` is a read-only mapping (`MappingProxyType`) with a dict serializer. From the C-019 review. 2 focused tests added; gate green (199 pytest, ruff, doctor). (PR pending.)
- 2026-06-19 - **C-049** (urgent, todo) + **C-050** (todo) added from the C-019 code-review checkpoint: C-049 hardens plugin discovery to be fail-graceful (per-file import errors warn+skip) and makes `Job.raw` read-only; C-050 retires the walking-skeleton stubs and re-points the CLI once the real runner/output/CLI land (deps C-024/C-025/C-026).
- 2026-06-19 - **C-019** Session store on `chunk/C-019-session-store`: `core.auth.SessionStore` encrypts Playwright storage-state dictionaries with Fernet, stores a PBKDF2HMAC-derived machine key through keyring, supports save/load/exists/delete, rejects unsafe session names, and keeps encrypted session files under `~/.jobhunter/sessions/*.enc` by default. Gate green (`197` pytest, `ruff`, import smoke). Merged `9fb5ce0` (PR #39).
- 2026-06-19 - **C-018** Mock connector + fixtures on `chunk/C-018-mock-connector`: `core.connectors.MockConnector` loads deterministic jobs from `fixtures/jobs.json` or an injected fixture path, enforces `source = "mock"`, returns all jobs when no keywords are provided, and filters with a case-insensitive keyword match against title/description. Gate green (`188` pytest, `ruff`, import smoke). Merged `5acca79` (PR #38).
- 2026-06-19 - **C-015** Ollama provider on `chunk/C-015-ollama-provider`: `core.ai_providers.OllamaProvider` calls the local Ollama `/api/generate` endpoint with default model `llama3`, no auth, `stream: false`, and delegates prompt orchestration/parsing/scored immutable job copies to `AIEngine`; tests fake HTTP with `httpx.MockTransport`. Gate green (`182` pytest, `ruff`, import smoke). Merged `70c71f6` (PR #37).
- 2026-06-19 - **C-014** AI engine facade on `chunk/C-014-ai-engine-facade`: `core.ai_engine.AIEngine` wraps an injected async prompt provider, builds criteria/scoring prompts, batches score requests, parses provider JSON into JobHunter models, raises `AIEngineError` for invalid provider output, and returns scored `Job` copies without mutating inputs. Gate green (`176` pytest, `ruff`, import smoke). Merged `a9138e2` (PR #36).
- 2026-06-19 - **C-013** Batching util on `chunk/C-013-batching-util`: `core.ai_engine.batching.batch_items` splits sequences into order-preserving list batches, handles empty/exact/remainder cases, preserves item identity, and rejects non-positive batch sizes. Gate green (`170` pytest, `ruff`, import smoke). Merged `7bef68d` (PR #35).
- 2026-06-19 - **C-012** Job field-stripper on `chunk/C-012-job-field-stripper`: `core.ai_engine.scrub` exposes pure helpers that strip jobs to `id`, `title`, `company`, and `description` before provider calls; `build_score_jobs_prompt` now uses the shared scrubber. Gate green (`163` pytest, `ruff`, import smoke). Merged `d5565b6` (PR #34).
- 2026-06-19 - **C-011** Response parsers on `chunk/C-011-response-parsers`: `core.ai_engine.parsing` parses criteria JSON into `SearchCriteria`, applies scored-job JSON to immutable `Job` copies, preserves unmentioned jobs, ignores unknown scored IDs, and returns `None` for malformed or invalid provider output. Gate green (`159` pytest, `ruff`, import smoke). Merged `1532e86` (PR #33).
- 2026-06-19 - **C-010** Prompt builders on `chunk/C-010-prompt-builders`: `core.ai_engine.prompts` builds deterministic GENERATE_CRITERIA and SCORE_JOBS prompt strings from the SDD §5.2 contract, preserves profile text verbatim, emits compact criteria JSON, and limits job payloads to `id`, `title`, `company`, and `description`. Gate green (`152` pytest, `ruff`, import smoke). Merged `df227d5` (PR #32).
- 2026-06-19 - **C-008** Auth strategy resolver on `chunk/C-008-auth-strategy-resolver`: design sign-off accepted in chat for the contract-level resolver scope. `core.auth.auth_strategy.resolve_auth` now resolves ordered plugin `auth_methods` with injected OAuth/session providers and env-backed API keys, returns the first successful `AuthResult`, treats `none` as always authenticated, and warns + returns `None` when required auth is unmet. Gate green (`147` pytest, `ruff`, import smoke). Merged `7d96047` (PR #31).
- 2026-06-19 - **C-009** Plugin discovery on `chunk/C-009-plugin-discovery`: `core.runner.discover_plugins` loads concrete plugin classes from direct `*.py` files via importlib, skips private/base files, handles missing directories as empty, and keeps runner orchestration for later chunks. Added focused discovery tests across connector, provider, and profile-input contracts. Gate green (`140` pytest, `ruff`, import smoke). Merged `c1e32ad` (PR #30).
- 2026-06-19 - **C-048** Deterministic PR review-comment fetch on `chunk/C-048-pr-comments`: `jh.py pr-comments <#>` fetches a PR's review threads + issue comments via the capability-tiered GitHub auth, renders them (pure engine helper) or `--json`, and degrades clearly without API access. Also backfilled the C-047 merge hash `6805055`. 6 focused tests added; full gate `python tools/jh.py gate C-048` all-green (131 pytest, ruff clean, doctor PASS). Merged `e5ba1d8` (PR #29).
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
