# JobHunter — Statement of Work

**AI-Powered Job Search Aggregator**

| | |
|---|---|
| Prepared by | Abdelrahman (Squad 3 Lead, Dsquares) |
| Document Date | June 2026 |
| Version | **1.1 — Amended** (supersedes v1.0) |
| Target Audience | Development Team / Assignee |
| Classification | Internal / Confidential |
| Document Status | Final — Ready for Development |

---

## Changelog — what changed in v1.1

1. **Profile input added to scope** as a pluggable layer — v1 accepts typed text only; PDF/Word/image
   parsers are explicitly future drop-in plugins (see Scope, FR-11, OI list).
2. **Auth generalised** to an abstract ordered strategy (`oauth → api_key` fallback) across connectors
   and providers; reflected in the plugin rules and FR-05/FR-08.
3. **Model/auth specifics refreshed** for June 2026: Gemini default `gemini-3-flash` with restricted
   authorization API keys (+OAuth); OpenRouter fallback `deepseek-r1:free` (the old `deepseek-v4-flash:free`
   left the free tier).
4. **Filter precedence clarified** and an explicit **output module** (`core/output.py`) acknowledged.
5. **Version control** added as a constraint: local git over the whole project folder, remote deferred.

---

## 1. Executive Summary

JobHunter is an AI-powered desktop and CLI job search aggregator for individual job seekers. It searches
multiple job platforms, uses AI to generate smart search criteria from the user's profile, and scores
each result against the user's preferences — eliminating manual browsing of dozens of job boards.

The system is a plugin-based platform: new job connectors, AI providers, and profile-input parsers are
added as standalone files with zero changes to core engine code. It ships as a cross-platform desktop
application (Tauri + Vue) with a full CLI for power users and automation.

### 1.1 Problem Statement

Job searching across multiple platforms is repetitive, time-consuming, and poorly matched to the
candidate's actual profile. Existing tools either require expensive API access or produce generic,
keyword-only results. No tool combines multi-platform aggregation with genuine AI-driven matching and
criteria generation in a locally runnable, low-cost application.

### 1.2 Proposed Solution

- Plugin-based connector architecture: drop a `.py` file into a folder, it is automatically loaded.
- AI Engine with two modes: GENERATE (profile text → smart keywords + criteria) and SCORE (raw listings
  → ranked + annotated results).
- Pluggable profile input: typed text in v1, with PDF/Word/image parsers as future drop-ins.
- Multiple AI provider backends (Gemini, Ollama/llama3 local, OpenRouter cloud-free), all swappable via
  config, each declaring an ordered auth strategy.
- Cross-platform desktop UI (Tauri + Vue 3) and full-featured CLI (Python + Click + Rich).
- Session-based authentication for job platforms — user logs in once, credentials persisted safely.

---

## 2. Scope of Work

### 2.1 In Scope

| Component | Description | Phase |
|-----------|-------------|-------|
| Core Engine | Plugin loader, Job model, SearchCriteria model, Runner orchestrator | Phase 1 |
| AI Engine | GENERATE_CRITERIA and SCORE_JOBS operations, provider abstraction | Phase 1 |
| Profile Input layer | Pluggable parser interface + built-in text parser | Phase 1 |
| Auth strategy | Ordered `oauth → api_key` resolver + keyring/session store | Phase 1 |
| Gemini Provider | OAuth + authorization API key, token cache, `gemini-3-flash` calls | Phase 1 |
| Ollama Provider | Local llama3 via Ollama REST API (dev/testing) | Phase 1 |
| LinkedIn Connector | Playwright session auth, search scraping, pagination | Phase 1 |
| Indeed Connector | httpx-based scraper, no login, JSON extraction | Phase 1 |
| Mock Connector | Local JSON fixture loader for offline testing | Phase 1 |
| CLI Interface | Click + Rich: run, auth, configure, export | Phase 1 |
| Config System | YAML config with pydantic validation, env var overrides | Phase 1 |
| Output Module | CSV and JSON export via pandas (`core/output.py`) | Phase 1 |
| Session Store | Playwright storage_state manager, encrypted at rest | Phase 1 |
| Desktop UI | Tauri v2 + Vue 3: Criteria, Results, Settings views | Phase 2 |
| OpenRouter Provider | API-key auth, free model tier (Qwen3 Coder, DeepSeek R1) | Phase 2 |
| Dev Documentation | README, connector / provider / profile-input authoring guides | Phase 2 |

### 2.2 Out of Scope

- Automatic job application submission (apply on behalf of user).
- Multi-user or SaaS deployment — single-user local tool.
- LinkedIn OAuth API access for job data — not available to third-party apps.
- Proxy rotation or commercial anti-bot services.
- Mobile application.
- Real-time job alerts or push notifications (future phase).
- Wuzzuf, Bayt, or other regional connectors — post-Phase 2.
- PDF/Word/image profile parsing — architecture reserves the seam, but only text ships in v1.

### 2.3 Assumptions

- Target machine runs Windows 10/11 (primary) or Linux. macOS is secondary.
- The user has an active Google account for Gemini OAuth, or a Gemini authorization API key.
- The user has an active LinkedIn account for session-based scraping.
- Ollama is installed and running locally when the llama3 provider is selected.
- Python 3.11+ and Node.js 20+ are available on the development machine.
- Rust toolchain is available for Tauri builds (or the team uses the pre-built binary).
- The team has read and accepts each platform's ToS regarding automated access.
- Rate limits and scraping constraints are respected; the tool is for personal use only.

---

## 3. Deliverables

### 3.1 Phase 1 — Core Engine + CLI (Target: 3 weeks)

| ID | Deliverable | Description | Target Week |
|----|-------------|-------------|-------------|
| D-01 | Core package | `core/` with abstractions, models, runner, auth strategy | Week 1 |
| D-02 | Gemini Provider | `gemini_provider.py` — OAuth + authorization API key, token cache | Week 1 |
| D-03 | Ollama Provider | `ollama_provider.py` calling local Ollama REST API | Week 1 |
| D-04 | Indeed Connector | `indeed_connector.py` — httpx scraping + pagination | Week 2 |
| D-05 | LinkedIn Connector | `linkedin_connector.py` — Playwright session + storage_state | Week 2 |
| D-06 | Mock Connector | `mock_connector.py` loading from `fixtures/jobs.json` | Week 1 |
| D-07 | CLI Interface | `ui/cli/cli.py` — run, auth, configure, export | Week 3 |
| D-08 | Config System | `config.yaml` schema + pydantic validator + env override | Week 1 |
| D-09 | Output Module | `core/output.py` — CSV and JSON export, timestamped | Week 2 |
| D-10 | Test Suite | pytest: AI engine units, connector contract tests | Week 3 |
| D-11 | Profile Input layer | `base_profile_input.py` + built-in `text_input.py` | Week 1 |

### 3.2 Phase 2 — Desktop UI + OpenRouter (Target: 3 weeks after Phase 1)

| ID | Deliverable | Description | Target Week |
|----|-------------|-------------|-------------|
| D-12 | Tauri Shell | Rust/Tauri v2 backend, IPC bridge to Python sidecar | Week 4 |
| D-13 | Vue App | Vue 3 + Vite frontend: router, Pinia store, design system | Week 4 |
| D-14 | Criteria View | Profile input, AI Generate, editable chips, refine affordance | Week 5 |
| D-15 | Results View | Scored table, color bands, detail panel, export | Week 5 |
| D-16 | Settings View | Provider selector, API key fields, connector toggles | Week 5 |
| D-17 | OpenRouter Provider | `openrouter_provider.py` — Qwen3 Coder + DeepSeek R1 | Week 5 |
| D-18 | Windows Installer | `.msi` package via tauri build | Week 6 |
| D-19 | Documentation | README, CONNECTOR_GUIDE, PROVIDER_GUIDE, PROFILE_INPUT_GUIDE | Week 6 |

---

## 4. Milestones & Timeline

### 4.1 High-Level Schedule

| Milestone | Target | Description | Phase |
|-----------|--------|-------------|-------|
| M-01 | Week 1 | Scaffolding, core abstractions, config, both AI providers, mock connector, text profile input | Phase 1 |
| M-02 | Week 2 | Indeed + LinkedIn connectors, end-to-end pipeline on CLI | Phase 1 |
| M-03 | Week 3 | Full CLI, output module, test suite, Phase 1 review | Phase 1 |
| M-04 | Week 4 | Tauri shell + Vue app scaffolded, IPC functional | Phase 2 |
| M-05 | Week 5 | All three UI views functional, OpenRouter integrated | Phase 2 |
| M-06 | Week 6 | Windows installer, documentation, final QA | Phase 2 |

### 4.2 Acceptance Gates

| Gate | Acceptance Criteria |
|------|---------------------|
| M-03 Gate | CLI can: (1) accept a plain-text profile, (2) generate criteria using Gemini, (3) run LinkedIn + Indeed connectors, (4) score and rank results, (5) export to CSV. All passing with llama3 as fallback. |
| M-06 Gate | Desktop app replicates all CLI functions. Windows `.msi` installs and runs cleanly on a clean Windows 11 machine. OpenRouter provider returns scored results. Authoring guides are peer-reviewed. |

---

## 5. Technical Constraints & Guidelines

### 5.1 Plugin System Rules (non-negotiable)

- Every connector inherits `BaseConnector` and implements `search(criteria) -> list[Job]`.
- Every AI provider inherits `BaseAIProvider` and implements `generate_criteria` and `score_jobs`.
- Every profile-input parser inherits `BaseProfileInput` and implements `to_text(source) -> str`.
- No connector, provider, or profile-input may import from another — they are independent.
- The runner discovers plugins at startup using `importlib`; no registration file is allowed.
- Files dropped into `connectors/`, `ai_providers/`, or `profile_inputs/` load identically to built-ins.

### 5.2 Authentication Rules

- No credentials (passwords, API keys, tokens) are ever hardcoded or committed to source control.
- Plugins declare an ordered `auth_methods` list; the runner resolves it (`oauth` preferred, `api_key`
  fallback, `session` for browser connectors, `none` for local).
- Google OAuth tokens stored in a platform-appropriate secure store (Windows Credential Manager / keyring).
- Gemini API keys must be restricted **authorization keys** (unrestricted standard keys are deprecated
  through 2026); read from an env var, never committed.
- LinkedIn session cookies stored via Playwright storage_state in an encrypted local file.
- All other API keys read from environment variables (config holds the env-var NAME, not the value).

### 5.3 Scraping Ethics & Rate Limiting

- All connectors implement a configurable delay between requests (default 2–5s randomised).
- LinkedIn connector uses a visible (non-headless) browser for the initial login flow.
- No connector performs more than 50 requests per session without a user-configured override.
- This tool is for personal use only. Reselling or distributing scraped data is prohibited.

### 5.4 Tech Stack (Fixed)

| Component | Specification |
|-----------|---------------|
| Python | 3.11 or higher |
| Playwright | Latest stable — async API |
| httpx | Latest stable — async, http/2 |
| Tauri | v2 (latest stable) |
| Vue | 3 with Composition API + Vite |
| Pinia | State management for Vue |
| Click | CLI framework |
| Rich | Terminal output formatting |
| Pydantic | v2 — config and model validation |
| Pytest | Test framework with pytest-asyncio |
| Pandas | Output formatting and CSV/JSON export |
| PyYAML | Config file parsing |

### 5.5 Version Control

Local git over the whole project folder (docs + code) from commit one. `output/` is git-ignored. Remote
(Bitbucket / GitHub) is deferred — initialise locally for history and progress tracking.

---

## 6. Acceptance Criteria

### 6.1 Functional Requirements

| ID | Requirement | Acceptance Criteria | Priority |
|----|-------------|---------------------|----------|
| FR-01 | Criteria Generation | Given a plain-text profile/CV, the AI engine generates a SearchCriteria object with titles, keywords, seniority, locations, and exclude terms. | Must Have |
| FR-02 | Job Scoring | Each Job is scored 0-100 with a match_reason and optional red_flags list. | Must Have |
| FR-03 | LinkedIn Search | Connector retrieves up to 50 jobs via persisted session. | Must Have |
| FR-04 | Indeed Search | Connector retrieves up to 50 jobs without login. | Must Have |
| FR-05 | Provider Swap | Changing `ai.provider` (and restarting) switches the active provider, resolving its `auth_methods`, with no code change. | Must Have |
| FR-06 | Connector Drop-in | A new connector `.py` in `connectors/` is auto-loaded on next run. | Must Have |
| FR-07 | CSV Export | Results exported to `output/results_<timestamp>.csv` with all Job fields including score. | Must Have |
| FR-08 | CLI Auth Flow | `jobhunter auth google` runs OAuth (or uses the authorization API key) and caches the token; `jobhunter auth linkedin` opens Playwright for manual login and saves storage_state. | Must Have |
| FR-09 | Desktop UI Run | Clicking Run triggers the full pipeline and populates the Results view. | Must Have |
| FR-10 | Settings Persistence | Settings changes are written to config.yaml and survive restart. | Must Have |
| FR-11 | Profile Input (text) | Typed profile text is normalised through the Profile Input layer; criteria can be refined in a follow-up step (multi-turn). | Must Have |

### 6.2 Non-Functional Requirements

| ID | Category | Requirement | Priority |
|----|----------|-------------|----------|
| NFR-01 | Performance | Full pipeline (generate + 2 connectors + score 50 jobs) under 3 minutes on a standard laptop. | Must Have |
| NFR-02 | Reliability | If one connector or auth method fails, the runner logs it and continues. | Must Have |
| NFR-03 | Security | No credential stored in plain text; tokens encrypted or in OS credential vault. | Must Have |
| NFR-04 | Portability | CLI runs on Windows 11, Ubuntu 22.04, macOS 14 without modification. | Should Have |
| NFR-05 | Installer size | Windows `.msi` under 120MB. | Should Have |
| NFR-06 | Startup time | Desktop app interactive within 5 seconds of launch. | Should Have |

---

## 7. Risks & Mitigations

| ID | Risk | Likelihood | Mitigation |
|----|------|-----------|------------|
| R-01 | LinkedIn anti-bot detection blocks scraping | High | Human-like delays + storage_state to avoid repeated logins; stealth headers; graceful failure with clear message. |
| R-02 | Indeed changes its JSON structure | Medium | Isolate parsing in a dedicated parser class, easy to update. |
| R-03 | Gemini quota/auth changes (e.g. standard-key deprecation, free-tier limits) | Medium | Use restricted authorization keys + OAuth; Gemini Flash free tier ~1,500 req/day; auto-fallback to Ollama/llama3. |
| R-04 | OpenRouter free model slugs change | Medium | Treat model IDs as config; verify `:free` slugs at build time; keep a documented fallback. |
| R-05 | Tauri-Python IPC adds latency/complexity | Medium | Python core as a sidecar subprocess; JSON over stdin/stdout — simple, well-tested. |
| R-06 | Playwright install fails on some Windows environments | Low | Provide `playwright install --with-deps` script; document firewall/AV issues. |

---

## 8. Approval & Sign-Off

This document requires sign-off from the following before development begins:

| Role | Name | Signature / Date |
|------|------|------------------|
| Sponsor / Product Owner | | |
| Tech Lead / Dev Assignee | | |
| QA Sign-off | | |

*Document prepared by: Abdelrahman, Squad 3 Lead — Dsquares. For questions regarding this SOW, contact
the document owner prior to development commencement.*

*End of Statement of Work — v1.1*
