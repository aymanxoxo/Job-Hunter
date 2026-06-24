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
| 003 | Gemini auth + model choice (authorization key/OAuth, `gemini-3-flash`) | Superseded by 027 | 2026-06-17 |
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
| 019 | Capability-based PR creation and handoff | Accepted | 2026-06-18 |
| 020 | Deterministic workflow automation harness | Accepted | 2026-06-18 |
| 021 | CI-gated auto-merge for explicitly allowed PR classes | Accepted | 2026-06-18 |
| 022 | CI-native opt-in auto-merge and pre-chunk merge-policy prompt | Accepted | 2026-06-18 |
| 023 | Long-running operations are async-by-default; `--wait` is opt-in and bounded | Accepted | 2026-06-19 |
| 024 | Machine-readable chunk registry as the single source of truth | Accepted | 2026-06-19 |
| 025 | Decouple the generic workflow engine from project business | Accepted | 2026-06-19 |
| 026 | Generated PROGRESS orientation and merge-hash sync | Accepted | 2026-06-19 |
| 027 | Gemini default model slug refresh (`gemini-3.5-flash`) | Accepted | 2026-06-24 |

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


## ADR-019 — Capability-based PR creation and handoff

**Context.** Different AI runtimes have different GitHub capabilities. Some can create a fully formed
pull request; others can push a branch but cannot open a PR; others may only be able to hand off a diff.
The project still needs consistent review quality and a clear user merge gate regardless of the agent.

**Decision.** Each AI agent takes the workflow as far as its available git/GitHub access allows. If it
can create a PR, it does so and gives the user the PR URL. If it cannot create a PR but can push a
branch, it pushes the branch and gives the user the GitHub compare/new-PR URL. If it cannot push, it
provides the diff/patch plus the exact PR title and description for manual creation. Every PR or manual
handoff includes a clear title (with chunk ID when applicable), a human-readable description, the Design
note, red→green test evidence, full gate evidence, and a one-line risk read. The user remains the
review/merge gate.

**Consequences.** Review handoffs are consistent across AI tools without baking in model-specific rules.
More capable environments remove manual steps; constrained environments still preserve enough context for
the user or another agent to create the same PR. This clarifies ADR-015 without changing its merge-gate
rule.


## ADR-020 — Deterministic workflow automation harness

**Context.** The project is intentionally strict and AI-oriented, but repeated mechanical work still
burns model tokens: environment setup, chunk readiness checks, stale ledger detection, validation gates,
PR evidence formatting, PR creation fallback, and post-merge cleanup. These tasks are deterministic and
should not be re-reasoned by every agent.

**Decision.** Add a repo-owned workflow harness at `tools/jh.py`. Agents start with
`python tools/jh.py bootstrap`, `status`, and `next`; validate with `doctor` and `gate`; generate PR
handoffs with `pr-ready`; create PRs or fall back per ADR-019 with `create-pr`; and use `after-merge` for
tag/branch cleanup. Direct PR creation checks authenticated `gh`, OAuth device flow captured by
`auth-login`, environment tokens (`JH_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`), then Git Credential
Manager via `git credential fill`. The harness is Python stdlib plus existing project tools, writes full
logs only under git-ignored `output/agent/`, and is backed by CI.

**Consequences.** Token use shifts away from repetitive project-state reconstruction and manual gate
formatting toward actual design/code judgment. Quality improves for rules that can be checked
deterministically. Cost: the harness itself becomes maintained project infrastructure and must stay small,
testable, and updated when the workflow changes.


## ADR-021 — CI-gated auto-merge for explicitly allowed PR classes

**Context.** Some PRs are fully mechanical and covered by deterministic checks. For those, requiring a
manual merge click after green CI adds delay without improving review quality. The user explicitly allowed
auto-merge when CI thoroughly checks the change.

**Decision.** Auto-merge is permitted only through `python tools/jh.py merge-pr <PR_NUMBER>` and only for
PR classes the user has allowed. The command checks GitHub directly and refuses to merge unless the PR is
open, non-draft, mergeable, and all check runs/statuses for the exact head SHA have completed with
`success`. It merges with the checked head SHA to avoid racing a changed branch. Missing, pending, failed,
or unknown CI blocks the merge with a clear reason.

**Consequences.** Mechanical PRs can land without another user click once CI is green. Risk remains bounded
because the default still blocks uncertain states, and higher-risk/product-design chunks still require
explicit user approval before auto-merge is used.


## ADR-022 — CI-native opt-in auto-merge and pre-chunk merge-policy prompt

**Context.** A separate agent-side wait loop works, but it still requires the agent session to stay alive.
The user asked for CI itself to merge when validations pass, controlled by a parameter/flag, and for agents
to ask before starting work whether the PR should auto-merge or wait for manual review.

**Decision.** The GitHub Actions CI workflow includes an `auto-merge` job that runs after validation. It
is a no-op unless the PR opts in with the `auto-merge` label or a checked `Auto-merge after CI` PR-body
checkbox. When opted in, CI calls `python tools/jh.py ci-auto-merge`, which uses the same readiness rules
as `merge-pr`, ignores its own in-progress check, merges only the exact checked head SHA, and deletes the
branch after merge. Agents must ask the user for the merge policy before starting a chunk or code change
and encode the answer in the PR.

**Consequences.** Green opted-in PRs can merge even if the agent disconnects. Manual review remains the
default because no label/checkbox means the CI job skips. The cost is stricter PR metadata discipline:
agents must capture the user's merge-policy choice before implementation.


## ADR-023 — Long-running operations are async-by-default; `--wait` is opt-in and bounded

**Context.** Agents hung for minutes inside a single tool call. `merge-pr <#> --wait 600` (the README's
normal flow) polled CI for up to 600s, and because readiness treated an already-merged PR as "not open →
not ready", an agent that ran `merge-pr` *after* CI had already merged the PR (and deleted the branch)
re-polled a closed PR for the full timeout before giving up. Branch deletion and CI auto-merge showed the
same "still waiting after it finished" symptom.

**Decision.** Agent-facing long operations are **async-by-default and idempotent**, with a fast,
non-blocking poll. `wait_for_pr_merge_readiness` short-circuits the moment a PR is already merged — no
check/status polling, no sleep — and reports `already_merged`; `merge-pr` / `ci-auto-merge` treat that as
immediate success and still run the (idempotent) branch delete. An already-absent branch is success, not
an error (`branch already absent`). `--wait` is opt-in and **hard-capped** at `MAX_WAIT_SECONDS` (300s)
via `clamp_wait_seconds`, so no agent path can block unbounded; `merge-pr` defaults to `--wait 0` (check
once). A new `pr-status <#>` command does a single non-blocking readiness read (`merged` / `ready` /
`pending`, `--json`) so agents poll between turns instead of holding the call open.

**Consequences.** Agents never sit in an unbounded blocking call, and re-running a merge/delete after the
op already completed returns success at once. Callers that want to block opt in with a bounded `--wait`;
CI's `ci-auto-merge` keeps a bounded wait (default 300s). The cost is a small, documented protocol change
(README/HANDOFF): poll `pr-status` rather than `merge-pr --wait 600`.


## ADR-024 — Machine-readable chunk registry as the single source of truth

**Context.** Per-chunk metadata lived in three hand-synced places: the PROGRESS.md ledger table
(status/deps/merge), `tools/jh_config.json` (risk flags, test mappings, smoke imports), and the dev-plan
§10 tables (goal/files/deps). Hand-syncing drifts — a dependency edited in one place and not the others —
and the harness had to scrape a markdown table to know the chunk graph.

**Decision.** `tools/chunks.json` is the single registry for per-chunk *static* metadata (title, stage,
`depends_on`, `risk_flagged`, `tests`) plus global `smoke_imports`; it absorbs and replaces
`jh_config.json`. `load_config` now derives its legacy `{risk_flagged_chunks, chunk_tests, smoke_imports}`
view from the registry, so existing callers are unchanged. `doctor` gains `check_registry_consistency`,
which fails if the registry, the PROGRESS ledger, and dev-plan §10 disagree on the chunk set, stage,
dependencies, or risk flags (dev-plan dependency ranges such as `C-010–C-013` are expanded before
comparison). Live status/merge intentionally stay hand-edited in PROGRESS.md for now; authority for those
moves to the registry in C-046 once generation exists, so this chunk introduces no new drift. (Proposed as
ADR-019; renumbered to 024 to follow the repo's ADR sequence.)

**Consequences.** One edit point for the chunk graph; the harness reads JSON instead of scraping markdown;
drift between the three trackers becomes a failing `doctor` check rather than a silent inconsistency. Cost:
the registry and the human-readable ledger coexist until C-046 wires generation.


## ADR-025 — Decouple the generic workflow engine from project business

**Context.** `tools/jh.py` mixed a reusable workflow engine (chunk graph, gate planning, PR readiness,
ledger parsing) with JobHunter specifics (file paths, gate commands, the `C-NNN` id format, plugin dirs,
risk list, CLI strings). That blocked reusing the *process* for another repo and concentrated everything
in one ~1.6k-line module.

**Decision.** Split into three modules: `tools/jh_engine.py` (the generic engine — value types plus pure
planning/evaluation logic, parameterized by an adapter, with **no** project identifiers),
`tools/jh_project.py` (the `ProjectConfig` adapter; the `JOBHUNTER` instance holds every project-specific
value), and `tools/jh.py` (the imperative CLI shell that wires the adapter into the engine and runs the
git/GitHub/file effects). `jh.py` re-exports engine names so its public surface — and all existing tests —
stay unchanged. A `doctor` check (`_check_engine_purity`) fails if `jh_engine.py` contains any forbidden
project identifier, and a fixture-adapter test drives the engine with a non-JobHunter `ProjectConfig` to
prove independence. (Proposed as ADR-020; renumbered to 025 to follow the repo's ADR sequence.)

**Consequences.** The process is now extraction-ready: another repo supplies a different `ProjectConfig`
and reuses the engine + shell unchanged (template / skill / agent / package — the target stays open). Cost:
a stable engine↔adapter boundary to maintain, and a few doc-format parsers (dev-plan dependency-range
expansion) still live in the shell pending a later generalization.


## ADR-026 - Generated PROGRESS orientation and merge-hash sync

**Context.** The top `PROGRESS.md` orientation block and done-chunk merge hashes were recurring drift
points. Agents had to hand-edit the same facts already present in the chunk graph and git history, and
`doctor` could detect stale merge placeholders only after the drift had already happened.

**Decision.** `PROGRESS.md` keeps live statuses and merge cells in its ledger, but the orientation block
between `jh:orientation` sentinels is generated by `python tools/jh.py sync`. The generic engine computes
last-done / next-ready / blocked from the ordered chunk graph; the project adapter supplies the sentinel
markers and static orientation lines; the CLI shell rewrites the file and backfills done-chunk merge
placeholders from git merge commits. `doctor` now fails if the on-disk generated block differs from what
`sync` would write, and `after-merge` invokes `sync` automatically.

**Consequences.** A cold agent still gets the same at-a-glance state, but the volatile lines are no
longer hand-maintained. Merge hashes can be recovered from git history instead of patched by docs-only
follow-ups. Cost: `PROGRESS.md` now has generated sentinels, and any manual edit inside them is treated as
drift to be regenerated.


## ADR-027 - Gemini default model slug refresh

**Context.** C-064 review found the previous default `gemini-3-flash` returns 404 against Google's
Gemini API. Google AI model documentation checked on 2026-06-24 lists the stable Flash model code as
`gemini-3.5-flash`, while the bare `gemini-3-flash` slug is not a valid default for the existing
`generateContent` provider path.

**Decision.** Update the built-in Gemini provider and default config to `gemini-3.5-flash`. Keep the
model configurable so users can select older or preview models explicitly, but do not ship a default
that fails every run before criteria generation or scoring can start.

**Consequences.** The out-of-box Gemini path works with the current model catalog again, and future
model churn remains a config change plus doc update. Cost: docs and tests that referred to the old
default need to treat ADR-003 as superseded.
