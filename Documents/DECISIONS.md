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
| 009 | Trunk-based, one commit per chunk, `[C-XXX]` + ledger as live tracker | Amended by 015 | 2026-06-17 |
| 010 | Tauri sidecar IPC over stdin/stdout JSON; logs stderr-only | Accepted | 2026-06-17 |
| 011 | Local git only, whole-folder tracking, remote deferred | Superseded by 014 | 2026-06-17 |
| 012 | Hierarchical `AGENTS.md` + mandatory documentation upkeep | Accepted | 2026-06-17 |
| 013 | Live Pipeline Progress UI as a first-class product feature | Accepted | 2026-06-17 |
| 014 | Remote (GitHub) dev/commit loop; AI as sole committer | Amended by 015 | 2026-06-17 |
| 015 | Feature-branch per chunk; user reviews & merges PRs | Accepted | 2026-06-17 |
| 016 | Per-chunk vertical protocol; risk-flagged design sign-off; walking skeleton | Accepted | 2026-06-17 |
| 017 | Per-chunk dual documentation (technical + business) | Accepted | 2026-06-17 |
| 018 | Strict config validation (`extra=forbid`) + immutable model containers | Accepted | 2026-06-18 |

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


## ADR-014 — Remote (GitHub) dev/commit loop; AI as sole committer

**Context.** ADR-011 chose local-git-only. In practice the Cowork sandbox file-mount cannot reliably
hold a `.git` directory (index corruption, truncated filenames, `null sha1`, stale/truncated reads), so
git cannot run against the user's folder from the sandbox. The user wanted the full
build → test → commit → push cycle automated rather than hand-committing each chunk.

**Decision.** Use a **private GitHub repo** (`github.com/aymanxoxo/Job-Hunter`) as the sync channel
instead of the file-mount. The AI keeps an **authoritative working clone in reliable sandbox-native
storage**, runs the full TDD loop there, and **commits + pushes to GitHub** via a fine-grained,
repo-scoped Personal Access Token (Contents: read/write). The user **pulls**. To prevent two-writer
divergence on `main`, the **AI is the sole committer**; the user only pulls, and routes any
externally-produced files (e.g. the Claude-design output) through the AI to be committed. Bitbucket was
ruled out — `bitbucket.org` is proxy-blocked from the sandbox; GitHub HTTPS is reachable.

**Consequences.** The broken mount is removed from the critical path and the loop is fully automated.
Trade-offs: a repo-scoped token lives in the sandbox **for the session only** (never stored in memory,
redacted in logs, user-revocable); the user must `git pull` to see changes and must **not** commit
locally while the AI is the committer; if a second writer is unavoidable, reconcile with `git pull
--rebase` before the next push. **Supersedes ADR-011.**


## ADR-015 — Feature-branch per chunk; user reviews & merges PRs

**Context.** ADR-014 had the AI commit and push directly to `main` as sole committer. The user wanted a
safer model where a conflict becomes a conversation rather than a broken `main`, and where changes are
reviewable before they land.

**Decision.** Each chunk is built on a short-lived branch `chunk/C-XXX-slug` with one clean commit
(`[C-XXX]` convention, TDD). The AI **pushes the branch only** — never directly to `main`. GitHub prompts
the user to open a PR; the **user reviews and merges** it. (The repo-scoped token is Contents-only — enough
for the AI to push branches but not to open/merge PRs via API, by design.) Conflicts surface in the PR and
are discussed before merging. After merge, the AI pulls `main`, deletes the branch, and starts the next
chunk's branch.

**Consequences.** `main` changes only through reviewed merges the user controls; conflicts are visible and
discussable. Cost: a per-chunk merge click for the user. **Amends ADR-009** (no longer pure trunk-based;
short-lived branches are the norm) **and ADR-014** (AI pushes branches, is no longer sole committer to
`main`; the user is the merge gate). One-commit-per-chunk, `[C-XXX]` tagging, and the ledger conventions
are unchanged.


## ADR-016 — Per-chunk vertical protocol; risk-flagged design sign-off; walking skeleton

**Context.** All code is AI-written and models may be swapped mid-project; the user wants strong
guarantees against hallucinated or incomplete work, with steps done and validated one at a time rather
than a big-bang chunk.

**Decision.** Three process additions:
1. **Per-chunk vertical protocol (six checkpointed steps):** Design → Test (red) → Implement (green) →
   Refactor + DoD gate → Verify (anti-hallucination) → Land (PR with evidence). Each step is validated
   before the next; the PR carries the Design note plus pasted red→green→full-suite output, so review is
   of proof, not claims. (Detailed in Dev Plan §3.3; `.github/PULL_REQUEST_TEMPLATE.md` enforces it.)
2. **Risk-flagged design sign-off:** before coding, the AI assesses chunk risk. Higher-risk or
   under-specified chunks (auth resolver C-008, OAuth C-016/C-017, scrapers C-020/C-021, runner C-025,
   IPC C-031, progress UI C-033) pause after the Design step for the user's OK; routine chunks run the
   full vertical and are reviewed only at the PR.
3. **Walking skeleton first (C-039):** an early thin end-to-end slice with stub implementations proves
   the architecture and integration seams before the deep layered build; the real chunks replace the
   stubs.

**Consequences.** Tests authored-first and shown failing, plus captured command output in every PR, make
incomplete or hallucinated work visible. Per-chunk design decisions live in the PR's Design note
(escalated to an ADR when cross-cutting) — no per-chunk architecture files. Cost: the skeleton adds some
throwaway stub code; risk assessment adds a brief judgement step per chunk.


## ADR-017 — Per-chunk dual documentation (technical + business)

**Context.** Beyond code correctness, each chunk's *technical* workings and its *business/product*
rationale need durable, discoverable homes, so a future engineer, AI, or stakeholder understands both how
a piece works and why it matters — without re-reading all the code.

**Decision.** Every chunk produces two documentation facets, **each included only when it adds value**
("if needed / worth it" — trivial or pure-internal chunks may need neither):
- **Technical** → the affected module's `AGENTS.md` (per ADR-012), plus `docs/tech/<topic>.md` only when
  a mechanism is non-obvious and cross-cutting. Always summarized in the PR's Design note.
- **Business** → a short, chunk-tagged entry in the running `Documents/PRODUCT_NOTES.md` (user/product
  value + any business rules the chunk encodes), promoted to `docs/business/<topic>.md` when substantial.
  Summarized in the PR's "Business value / rules" field.
Both are **integrated into existing docs — no per-chunk doc files.** The §3.1 "docs synced" gate covers
both facets; the PR template prompts for each.

**Consequences.** Tech and business knowledge persist in low-rot, discoverable places and the author
decides explicitly each time. Cost: a per-chunk judgement on whether a note is warranted; `docs/tech/`
and `docs/business/` are created lazily on first use.


## ADR-018 — Strict config validation + immutable model containers

**Context.** A review of C-003/C-004 found three gaps: (1) pydantic silently dropped unknown config
keys, so a pasted secret (e.g. `auth.gemini_api_key: sk-…` or `connectors.linkedin.api_key`) stayed in
`config.yaml` without error — breaking the "always safe to commit" promise; (2) `frozen=True` blocked
attribute reassignment but `job.red_flags.append(...)` / `criteria.titles.append(...)` still mutated the
list in place; (3) `output.format` accepted any string and `delay_min > delay_max` was allowed.

**Decision.** (1) Every config sub-model and the root `Config` use `extra="forbid"`, so any unknown key
(including a stray secret) fails `load_config` loudly. (2) `Job.red_flags` and all `SearchCriteria`
sequence fields are `tuple[str, ...]` — construction still accepts lists (pydantic coerces), but the
stored value cannot be mutated in place. (3) `output.format` is `Literal["csv","json","both"]` and a
model validator enforces `delay_min <= delay_max`.

**Consequences.** The no-secrets guarantee and the immutability promise (ADR-008, SDD §5.2) are now
actually enforced, with tests. Cost: adding a new config field requires updating the model (extra is
forbidden) — intentional. Strengthens, does not supersede, ADR-002 / 006 / 008.
