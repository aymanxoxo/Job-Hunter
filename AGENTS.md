# JobHunter — AI agent guide (root)

> **Read this first.** This file is the map of the project. It orients any AI agent (or human) to the
> structure, conventions, and where to go for detail — without reading every file. It is the
> *orientation layer*; the design docs are the *spec layer*; the code is the *truth*.

## What JobHunter is

A locally-installed, **plugin-based AI job-search aggregator**. It scrapes job listings from multiple
platforms, uses AI to (a) generate structured search criteria from a user profile and (b) score raw
listings against that criteria, then presents the scored results through a CLI (Click/Rich) and a
desktop UI (Tauri v2 + Vue 3) that talks to the Python core over a stdin/stdout JSON sidecar.

Core principles: **plugin-first** (drop a `.py` file in a folder, it's auto-loaded — no registration),
**auth-safe** (no hardcoded credentials), **fail-graceful** (one connector failing doesn't stop the
pipeline), **dual interface** (same core for CLI + desktop), **AI-agnostic** (engine calls an abstract
provider interface).

## Documentation layers

| Layer | Where | Use it for |
|-------|-------|-----------|
| Orientation | `AGENTS.md` files (this one + per-module) | "What is this folder, where do I go next" |
| **Handoff** | [`HANDOFF.md`](HANDOFF.md) | **Start here if you are a new AI agent taking over** |
| Spec | [`Documents/JobHunter_SDD_v1.1.md`](Documents/JobHunter_SDD_v1.1.md) | How the system actually works — models, contracts, connector/provider specs, IPC, tests, build |
| Scope/plan | [`Documents/JobHunter_SOW_v1.1.md`](Documents/JobHunter_SOW_v1.1.md) | Scope, deliverables, milestones, acceptance criteria, risks |
| Dev plan | [`Documents/JobHunter_DEV_PLAN_v1.0.md`](Documents/JobHunter_DEV_PLAN_v1.0.md) | How we build it: chunk model, FP + logging standards, commit + ledger conventions, per-chunk DoD, progress-UI spec, full chunk list |
| Live tracker | [`PROGRESS.md`](PROGRESS.md) | Current state — last done / next ready / blocked + the chunk ledger. Read this first when picking up work |
| Decisions | [`Documents/DECISIONS.md`](Documents/DECISIONS.md) | ADR log — the *why* behind key architectural and process choices |
| Design | [`design/v1.1/`](design/v1.1/) — DESIGN.md + tokens.css + wireframes | UI/UX design system, tokens & wireframes — source for the Vue UI (C-032–C-036); versioned, current **v1.1** |

## Module index (planned)

The folder tree below is the SDD target. **Status: scaffolded (C-001)** — the `core/*` + `ui/cli` package tree, user drop-zones, and tooling (`pyproject.toml`, ruff, pytest) are in place; modules are empty stubs filled by later chunks.
Each module folder gets its own `AGENTS.md` (following the template below) when it is created.

| Module | Path | Purpose |
|--------|------|---------|
| Models | `core/models/` | `Job` and `SearchCriteria` dataclasses |
| Connectors (built-in) | `core/connectors/` | `BaseConnector` ABC + Mock (present); Indeed / LinkedIn planned |
| AI providers (built-in) | `core/ai_providers/` | `BaseAIProvider` ABC + Ollama (present); Gemini / OpenRouter planned |
| Auth | `core/auth/` | Ordered auth strategy resolver + encrypted session store; OAuth device flow planned |
| Engine | `core/ai_engine/` | AI facade + pure prompt/parsing/scrub/batching helpers |
| Runner | `core/runner.py` | Plugin loader (importlib) + pipeline orchestrator |
| Pipeline transforms | `core/pipeline.py` | Pure merge, URL dedup, score sort, and threshold filter helpers |
| Progress events | `core/progress.py` | Runtime progress JSONL emitter for CLI/desktop IPC |
| Connector drop-zone | `connectors/` | User-added connectors, auto-discovered |
| Provider drop-zone | `ai_providers/` | User-added providers, auto-discovered |
| Profile inputs (built-in) | `core/profile_inputs/` | `BaseProfileInput` ABC + `TextProfileInput` text passthrough |
| Profile input drop-zone | `profile_inputs/` | User-added profile parsers; PDF/Word/image are future drop-ins |
| CLI | `ui/cli/` | Click + Rich command interface; C-039 has a temporary walking-skeleton command |
| Desktop | `ui/desktop/` | Tauri v2 (Rust) shell + Vue 3 frontend |
| Fixtures | `fixtures/` | Mock connector data (`jobs.json`) |
| Output | `output/` | Generated results — **git-ignored** |
| Config | `config.yaml` | User configuration |
| Workflow tools | `tools/` | Deterministic AI workflow harness (`jh.py`) for bootstrap/status/gate/PR handoff |
| Design assets | `design/` | Versioned UI/UX (current `v1.1/`): `DESIGN.md`, `tokens.css`, wireframes — the UI source |

## Active design decisions (now folded into SDD/SOW v1.1)

These were agreed after v1.0 and are now incorporated into the v1.1 spec docs. Kept here as a quick
reference; the full rationale lives in [`Documents/DECISIONS.md`](Documents/DECISIONS.md), and the docs
are the authority.

1. **Auth is an abstract, ordered strategy** — `oauth → api_key` fallback, declared on the plugin and
   resolved by the runner. Applies to **both** base classes (providers for model auth; connectors keep
   site auth `none|session|oauth`). Replaces the SDD's plain `requires_api_key: bool`.
2. **Profile input is a new pluggable layer** in front of `GENERATE_CRITERIA`. v1 ships a built-in
   text-in-chat parser only; PDF / Word / image parsers are future drop-in plugins (same pattern as
   connectors/providers). Architecture must reserve the seam now.
3. **Profile interaction supports both modes** — one-shot (files+text together; only text wired in v1)
   and multi-turn refinement of the generated criteria afterward.
4. **Version control:** local git over the whole project folder (docs + code); `output/` git-ignored;
   remote deferred.

**Reconciled in v1.1:** output/export module now lives at `core/output.py`; `min_score_threshold` is the
single effective filter (seeded by `ai.min_score`); model IDs refreshed (Gemini → `gemini-3-flash`,
OpenRouter fallback → `deepseek-r1:free` since `deepseek-v4-flash:free` left the free tier; Gemini auth
uses restricted authorization keys + OAuth).

## Non-negotiable conventions

- Every connector inherits `BaseConnector` and implements `search(criteria) -> list[Job]`.
- Every provider inherits `BaseAIProvider` and implements `generate_criteria` + `score_jobs`.
- **No connector or provider imports from another** — plugins are independent.
- Discovery is via `importlib` at startup — no registration file.
- **No credentials in source or `config.yaml`** — config holds env-var *names*, values come from env or
  secure store (OS keyring / Windows Credential Manager). LinkedIn session encrypted at rest (Fernet).
- Connectors use a configurable randomised delay (default 2–5s) and ≤ 50 requests/session without an
  explicit override. Personal use only.

## Documentation upkeep (MANDATORY)

Keeping the documentation in sync with reality is **not optional**. Any change that affects what a doc
describes must be reflected in that doc *as part of the same change* — never deferred, never "later".

- **Scope.** This rule covers the spec docs ([`Documents/JobHunter_SDD_v1.1.md`](Documents/JobHunter_SDD_v1.1.md),
  [`Documents/JobHunter_SOW_v1.1.md`](Documents/JobHunter_SOW_v1.1.md)), the [dev plan](Documents/JobHunter_DEV_PLAN_v1.0.md),
  the [decisions log](Documents/DECISIONS.md), [`PROGRESS.md`](PROGRESS.md), this root `AGENTS.md`, and
  every per-module `AGENTS.md`.
- **Trigger.** If you add/rename/remove a module, change a contract or interface, alter config keys,
  swap a model/provider, change commands, or make any decision that amends the spec — update the
  affected doc(s) in the same commit. Apply the "if needed" judgement honestly: a pure internal
  refactor with no externally-visible change may need nothing, but anything a reader of the doc would
  now find wrong **must** be fixed.
- **Specifics.** New module folder → add its `AGENTS.md` (template below) **and** flip its row in the
  module index from *planned* to *present*. Spec change → bump the relevant doc, add a Changelog entry,
  and increment the version. New material decision → add an ADR entry to `DECISIONS.md`; don't leave it
  living only in chat or memory.
- **Single source of truth.** Update the one canonical place and fix links — never copy a fact into a
  second file to "keep them both current".
- **Definition of done.** A task is not complete while any doc it touched is stale. Treat a stale doc as
  a bug.

## Development workflow (how chunks get built)

Full detail in the [dev plan](Documents/JobHunter_DEV_PLAN_v1.0.md); the essentials:

- **Use the deterministic harness for mechanical work.** After C-040, start with
  `python tools/jh.py bootstrap`, `python tools/jh.py status`, and `python tools/jh.py next`; get the
  chunk brief with `python tools/jh.py context C-XXX`; sync generated progress state with
  `python tools/jh.py sync`; validate with `python tools/jh.py gate C-XXX`; generate/create PR handoffs
  with `pr-ready` and `create-pr`.
- **All work is AI-executed and chunk-based.** Not scrum — a dependency DAG of small chunks (`C-XXX`).
  A chunk is workable once its dependencies are `done`; pick any ready one from [`PROGRESS.md`](PROGRESS.md).
- **The loop:** read `PROGRESS.md` orientation block → take the next ready chunk → read its row + linked
  SDD § → write tests first (**TDD**) → implement until green → run the §3.2 validation sequence → set
  the ledger row to `done` (+ hash) → **one commit** on `main`.
- **Definition of Done (every chunk):** chunk tests green; full `pytest` green; `ruff` clean; FP +
  logging conventions honoured; only the chunk's scope touched; docs synced; ledger updated and
  `jh.py sync` run; exactly one commit. A chunk is not done while any of these is outstanding.
- **Commit format:** `<type>(<scope>): <summary>  [C-XXX]` with body lines `Tests:` and `Ledger: C-XXX → done`.
  The `[C-XXX]` tag joins plan ↔ ledger ↔ history, so `git log` reads as a progress diary.
- **Code style:** functional core / imperative shell — pure, single-job, testable functions; effects
  isolated in thin adapters; immutable models; inject time/uuid/random.
- **Logging:** structured, keyed to a per-run `run_id`, **stderr only** (stdout is the sidecar IPC
  channel — a stray stdout log corrupts it). Never log secrets.

### Chunk ownership — in-sandbox vs external agent

Every chunk has an implicit **executor**:

- **`self` (default)** — the in-sandbox Cowork agent builds it: pure Python with mocked I/O, fully
  testable in the sandbox / CI.
- **`external`** — a local coding agent with the full toolchain (Claude Code / Codex / Copilot on the
  developer's machine) owns it **end to end**, running the same per-chunk protocol (design → test →
  impl → gate → merge → ledger update). For any chunk needing a Rust/Tauri/Node toolchain or a GUI to
  build and test — which neither the sandbox nor GitHub Actions CI can fully do.

**Standing rule:** if a chunk can't be built *and* tested in the sandbox or in CI, it is `external`.
The in-sandbox agent never starts external chunks — it flags them and leaves them for a local agent.
(For a `self` chunk that hits a single sandbox-blocked step, prefer CI; otherwise the in-sandbox agent
hands the developer a copyable A-to-Z prompt for an external agent.)

**Currently `external`** (Phase-2 desktop; also deferred until Phase 1 is complete): **C-031** Tauri
shell + sidecar + IPC, **C-032** Vue scaffold, **C-033** Live Pipeline Progress UX, **C-034–C-036**
views, **C-037** Windows installer. When Phase 1 finishes, a local agent picks these up from
[`PROGRESS.md`](PROGRESS.md) and runs them A-to-Z. Everything else (providers, connectors incl. the
Adzuna aggregator, pipeline, CLI, docs) is `self` and built in-sandbox.

## Commands (planned — from SDD §13)

```bash
# Python env
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
playwright install chromium --with-deps
# Run
jobhunter run --profile "Senior Python developer seeking remote work"  # C-039 skeleton CLI
# Desktop (needs Node 20+, Rust toolchain)
cd ui/desktop && npm install && npm run tauri dev
# Tests
pytest tests/ -v --asyncio-mode=auto
```

## Tech stack (fixed)

Python 3.11+, Playwright (async), httpx (async/http2), Pydantic v2, Click, Rich, PyYAML, Pandas,
Pytest+pytest-asyncio; Tauri v2, Vue 3 (Composition API) + Vite, Pinia.

## Template for per-folder AGENTS.md

When you create a module folder, add an `AGENTS.md` using this skeleton. Keep it short — describe only
what is *local* to that folder; link, don't duplicate.

```markdown
# <folder> — <one-line purpose>
## Contents      — each file → one-line description
## Contracts     — interfaces/rules anything here must honor (omit if none)
## Conventions   — local patterns, gotchas
## Pointers      — parent AGENTS.md, related modules, relevant SDD section
```

Rules of thumb: only add a file where a folder's content is non-obvious or carries a contract (trivial
folders inherit from their parent); never copy facts between files; update the AGENTS.md in the same
commit as the code it describes.
