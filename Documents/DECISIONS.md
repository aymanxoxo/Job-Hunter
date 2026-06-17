# JobHunter — Architecture Decision Log

> The **why** behind the project's key architectural and process choices. Each entry is a lightweight
> ADR: Context (why it came up) → Decision (what we chose) → Consequences (trade-offs / follow-ons).
> The spec docs (SDD/SOW/Dev Plan) describe *what* the system is; this log preserves *why* it is that
> way, so a model picking up the project doesn't relitigate settled choices. Add a new entry whenever a
> material decision is made; never edit a superseded entry — append a new one and mark the old `Superseded`.

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| 001 | Plugin-first architecture via importlib drop-zones | Accepted | 2026-06-17 |
| 002 | Abstract, ordered auth strategy (`oauth → api_key`) | Accepted | 2026-06-17 |
| 003 | Gemini auth + model choice (authorization key/OAuth, `gemini-3-flash`) | Accepted | 2026-06-17 |
| 004 | OpenRouter model selection (`qwen3-coder:free` + `deepseek-r1:free`) | Accepted | 2026-06-17 |
| 005 | Pluggable Profile Input layer (text-only v1) | Accepted | 2026-06-17 |
| 006 | Filter precedence: `min_score_threshold` is the single effective filter | Accepted | 2026-06-17 |
| 007 | Explicit output module at `core/output.py` | Accepted | 2026-06-17 |
| 008 | Functional core / imperative shell + TDD per chunk | Accepted | 2026-06-17 |
| 009 | Trunk-based, one commit per chunk, `[C-XXX]` + ledger as live tracker | Accepted | 2026-06-17 |
| 010 | Tauri sidecar IPC over stdin/stdout JSON; logs stderr-only | Accepted | 2026-06-17 |
| 011 | Local git only, whole-folder tracking, remote deferred | Accepted | 2026-06-17 |
| 012 | Hierarchical `AGENTS.md` + mandatory documentation upkeep | Accepted | 2026-06-17 |
| 013 | Live Pipeline Progress UI as a first-class product feature | Accepted | 2026-06-17 |

---

## ADR-001 — Plugin-first architecture via importlib drop-zones

**Context.** The product must support new job sites and AI backends over time without touching core
engine code, and let the user add their own. A registration file or central wiring would become a
bottleneck and a merge point.

**Decision.** Connectors, AI providers, and profile-input parsers are discovered at startup by scanning
directories (built-in + user drop-zones `connectors/`, `ai_providers/`, `profile_inputs/`) with
`importlib`, inspecting each module for subclasses of the relevant ABC. A drop-in file = one class
inheriting the base; no registration.

**Consequences.** Maximum extensibility and zero-wiring UX. Cost: dynamic loading needs careful error
isolation (a bad plugin must not crash discovery) and a contract test every plugin must pass. Plugins
may not import one another — they stay independent.

## ADR-002 — Abstract, ordered auth strategy (`oauth → api_key`)

**Context.** v1.0 modelled provider auth as a single `requires_api_key: bool`. Real backends differ:
some support OAuth, some only API keys, some none (local). The user asked for "OAuth whenever available,
API-key fallback" generalised across all pluggable backends, not just Gemini.

**Decision.** Each plugin declares an ordered `auth_methods` list (e.g. `['oauth', 'api_key']`,
`['session']`, `['none']`). A single runner-side resolver tries each in priority order; first success
wins; if none succeed and auth is required, the plugin is skipped with a clear log (fail-graceful). The
same mechanism covers both `BaseConnector` (site auth) and `BaseAIProvider` (model auth).

**Consequences.** One uniform, testable auth path; graceful degradation; easy to add new methods. Cost:
slightly more machinery than a boolean. Supersedes the v1.0 `requires_api_key` / single `auth_type`.

## ADR-003 — Gemini auth + model choice

**Context.** v1.0 specified Gemini via "OAuth 2.0 device flow" against the AI Studio free-tier endpoint
and model `gemini-2.5-flash`. Verified against June 2026 reality: the AI Studio free tier authenticates
with **API keys**, Google is **deprecating unrestricted standard keys** (rejected from 19 Jun 2026,
all standard keys by Sept 2026) in favour of restricted *authorization keys*, and `gemini-2.5-flash`
has largely been superseded by `gemini-3-flash` as the recommended free-tier default.

**Decision.** Gemini declares `auth_methods = ['oauth', 'api_key']`. The API-key path uses a **restricted
authorization key**; OAuth (device flow) is preferred where the user has client credentials configured.
Default model `gemini-3-flash` (2.5 Flash / Flash-Lite remain selectable via config). Free tier
~1,500 req/day is ample for personal use; auto-fallback to Ollama/llama3 on failure.

**Consequences.** Resilient to the 2026 key-deprecation timeline; model is config-driven so future
swaps are trivial. Cost: two auth paths to maintain (covered by ADR-002's resolver).

## ADR-004 — OpenRouter model selection

**Context.** v1.0 named `qwen/qwen3-coder:free` (default) and `deepseek/deepseek-v4-flash:free`
(fallback). Verified June 2026: `qwen3-coder:free` is current and strong; `deepseek-v4-flash:free` has
**left the free tier**. OpenRouter free slugs rotate over time.

**Decision.** Default `qwen/qwen3-coder:free`, fallback `deepseek/deepseek-r1:free`. Treat model IDs as
config, require the `:free` suffix, and re-verify slugs at implementation time against OpenRouter's model
list. OpenRouter is API-key only (`auth_methods = ['api_key']`).

**Consequences.** Avoids a dead default. Ongoing: free-tier slugs and limits drift, so this is a
"verify-at-build" dependency, flagged in SDD §7.3 and risk R-04.

## ADR-005 — Pluggable Profile Input layer (text-only v1)

**Context.** The user wants profile input to accept text, PDF, Word, and images eventually, but didn't
want image/PDF parsing complexity in v1. The engine should stay input-format-agnostic.

**Decision.** Introduce a `BaseProfileInput` contract that normalises any source to plain text
(`to_text`) before `GENERATE_CRITERIA`. v1 ships only `TextProfileInput`; PDF/Word/image parsers are
future drop-ins in `profile_inputs/` (image parsers may use local OCR or a multimodal provider — internal
to the plugin). Profile interaction supports both one-shot (files+text) and multi-turn refinement.

**Consequences.** New formats are added without touching the engine. Cost: an extra abstraction now for
a feature only partially used in v1 — justified by the explicit roadmap and the plugin philosophy.

## ADR-006 — Filter precedence

**Context.** v1.0 had two knobs for the same thing: `config.ai.min_score` and
`SearchCriteria.min_score_threshold`, with no stated precedence.

**Decision.** `SearchCriteria.min_score_threshold` is the single effective filter applied at pipeline
sort/filter; `config.ai.min_score` only seeds its default when criteria are generated. User edits to the
threshold win.

**Consequences.** Removes ambiguity; one place governs filtering.

## ADR-007 — Explicit output module

**Context.** v1.0 listed an output/export deliverable but no file for it in the folder tree.

**Decision.** The exporter lives at `core/output.py` (timestamped CSV/JSON via pandas), with pure
serialisation logic separated from the file-write edge.

**Consequences.** Closes a spec gap; the writer is unit-testable as a pure transform plus a thin sink.

## ADR-008 — Functional core / imperative shell + TDD per chunk

**Context.** All code is written and tested by AI models; the user requires functional-style code where
each function does one testable, traceable job. Models swap mid-project, so correctness must be
self-evident from tests.

**Decision.** Pure, single-job functions hold all logic (deterministic, no I/O, inject time/uuid/random);
side effects live in thin adapters at the edges; orchestrators (`runner`, `ai_engine`) compose them.
Every chunk is built test-first (TDD); the test is the chunk's executable spec.

**Consequences.** High testability and traceability; easy fakes; clean diffs. Cost: more, smaller
functions and explicit dependency passing — accepted as the point.

## ADR-009 — Trunk-based, one commit per chunk, ledger as live tracker

**Context.** Because models are swapped mid-build, re-deriving "where are we" from the codebase is
expensive. We need cheap, reliable orientation.

**Decision.** Work is a dependency DAG of small chunks (`C-XXX`). One descriptive commit per chunk on
`main` (`<type>(<scope>): <summary>  [C-XXX]`), TDD authored within it. `PROGRESS.md` holds an
orientation block + chunk ledger, updated in the same commit. Plan + ledger + `git log` (joined by the
`[C-XXX]` tag) are three views of one truth.

**Consequences.** A fresh model orients in ~10 lines + a `git log`. Cost: discipline to keep the ledger
in lockstep (enforced by the per-chunk Definition of Done). No scrum artifacts — they coordinate humans,
and no human works here.

## ADR-010 — Tauri sidecar IPC; logs stderr-only

**Context.** The desktop app needs to call the Python core. A REST server adds deployment complexity for
a single-user local tool.

**Decision.** The Python CLI runs as a Tauri sidecar subprocess; communication is line-delimited JSON
over stdin/stdout (`run_pipeline` request; streamed `progress`; final `result`). Because **stdout is the
IPC channel**, all diagnostic logging goes to **stderr** — a hard rule. Logs are structured and keyed to
a per-run `run_id`.

**Consequences.** Simple, portable, no server. Critical constraint: a stray `print`/stdout log corrupts
the IPC stream, so logging discipline is enforced in code review and the logging helper.

## ADR-011 — Local git only, whole-folder tracking

**Context.** The user wants progress history but no remote yet, and wants docs tracked alongside code.

**Decision.** Initialise git locally over the entire project folder (docs + code); `output/` git-ignored;
remote (Bitbucket/GitHub) deferred. Note: git must be run on the user's own machine — the Cowork sandbox
mount cannot reliably hold a `.git` directory (see ADR note / chat history), so the AI proposes content
and the user owns all git operations.

**Consequences.** Full local history with zero remote setup. Operational constraint: git actions are the
user's responsibility; the AI never runs destructive or repo-modifying git commands against the folder.

## ADR-012 — Hierarchical AGENTS.md + mandatory documentation upkeep

**Context.** The project must be AI-friendly as it grows: a model should understand any folder without
deep-reading every file, and docs must not rot.

**Decision.** A root `AGENTS.md` is the map; per-module `AGENTS.md` files are added only where content is
non-obvious, following a fixed short template. Keeping docs in sync is a **mandatory** rule: any change
that makes a doc stale is fixed in the same change. `AGENTS.md` is canonical; a one-line `CLAUDE.md`
points to it for Claude Code.

**Consequences.** Cheap orientation, low drift. Cost: doc updates are part of every change's Definition
of Done (treated as a feature, not overhead).

## ADR-013 — Live Pipeline Progress UI as a first-class feature

**Context.** The user requires the app to show detailed pipeline progress with genuinely good UX — not a
spinner, not ugly.

**Decision.** A dedicated, polished progress component (chunk C-033): a five-stage timeline
(profile → criteria → search → score → export) driven live by the streamed IPC `progress` events, with
per-connector sub-rows, a determinate scoring bar, graceful partial-failure (amber, non-blocking) states,
consistent score-band colors, reduced-motion support, and no layout shift. Fully data-driven — the
component holds no business logic.

**Consequences.** A standout UX and a clear, testable contract between the core's event stream and the
UI. The same event stream also drives the CLI's Rich rendering (one emitter, two renderers). Distinct
from the *dev* progress ledger (`PROGRESS.md`), which tracks build state, not runtime state.
