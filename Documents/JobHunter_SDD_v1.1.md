# JobHunter — Software Design Document

**AI-Powered Job Search Aggregator**

| | |
|---|---|
| Prepared by | Abdelrahman — Squad 3 Lead, Dsquares |
| Date | June 2026 |
| Version | **1.1 — Amended** (supersedes v1.0) |
| Companion | JobHunter SOW v1.1 |
| Classification | Internal / Confidential |

---

## Changelog — what changed in v1.1

v1.1 folds in design decisions taken after v1.0 was written, plus reconciliations of inconsistencies
found during review. Substantive changes:

1. **Auth is now an abstract, ordered strategy** (`oauth → api_key` fallback) declared on each plugin
   and resolved by the runner — applied to both `BaseConnector` and `BaseAIProvider`. Replaces the
   plain `requires_api_key: bool`. See §4 and §8.
2. **New pluggable Profile Input layer** in front of `GENERATE_CRITERIA`. v1 ships a built-in
   text parser only; PDF/Word/image parsers are future drop-in plugins. See §3.3 and §5.3.
3. **Profile interaction supports two modes** — one-shot (files+text together) and multi-turn
   refinement. v1 wires text-only one-shot + refinement. See §10 and §11.
4. **Output/export module given an explicit home**: `core/output.py`. See §2 and §5.4.
5. **Filter precedence reconciled**: `SearchCriteria.min_score_threshold` is the single effective
   filter; `ai.min_score` in config is only its default seed. See §9.
6. **Model IDs refreshed** against June 2026 availability: Gemini default → `gemini-3-flash`
   (2.5 Flash/Flash-Lite still selectable); OpenRouter fallback `deepseek-v4-flash:free` removed
   (no longer free) → `deepseek-r1:free`; Gemini auth uses restricted "authorization" API keys (+OAuth)
   as standard unrestricted keys are being phased out in 2026. See §7.
7. **Version control**: local git over the whole project folder; `output/` git-ignored; remote deferred.

---

## 1. System Overview

JobHunter is a locally-installed, plugin-based job search aggregator. It scrapes job listings from
multiple platforms, uses AI to both generate intelligent search criteria from a user profile and score
raw job results against those criteria, and presents the scored output through a CLI and a desktop UI.

### 1.1 Core Design Principles

- **Plugin-first**: every connector, AI provider, and profile-input parser is a drop-in file — no
  registration, no wiring.
- **Auth-safe**: no credential is ever hardcoded; an ordered auth strategy (OAuth where available, API
  key otherwise) plus the OS keyring is used wherever possible.
- **Fail-graceful**: connector failures are isolated; the pipeline continues with the remaining sources.
- **Dual interface**: the same Python core is consumed by both CLI (Click/Rich) and desktop (Tauri
  sidecar IPC).
- **AI-agnostic**: the engine does not know which provider it is calling — it calls through an abstract
  interface.

### 1.2 High-Level Data Flow

One full pipeline execution:

| Step | Action | Details |
|------|--------|---------|
| 1 | User supplies profile (typed text in v1; files in future) | CLI prompt or Criteria View; passes through the Profile Input layer → plain text |
| 2 | AI Engine: GENERATE_CRITERIA | Calls active AI provider → returns `SearchCriteria` object |
| 3 | Runner discovers enabled connectors | `importlib` scans `connectors/` at startup |
| 4 | Each connector runs `search(criteria)` | Parallel async execution, results merged into `[Job]` list |
| 5 | AI Engine: SCORE_JOBS | Batches jobs (15/call), calls provider → annotated `[Job]` list |
| 6 | Output module writes results | `core/output.py` → CSV + JSON to `output/`, timestamped |
| 7 | UI layer renders scored results | CLI table (Rich) or desktop Results View (Vue) |

---

## 2. Repository & Folder Structure

```
job_hunter/
├── core/
│   ├── models/
│   │   ├── job.py                  # Job dataclass
│   │   └── search_criteria.py      # SearchCriteria dataclass
│   ├── connectors/
│   │   ├── base_connector.py       # ABC — plugin contract
│   │   ├── indeed_connector.py     # Built-in: Indeed (httpx)
│   │   ├── linkedin_connector.py   # Built-in: LinkedIn (Playwright)
│   │   └── mock_connector.py       # Built-in: offline fixture
│   ├── ai_providers/
│   │   ├── base_provider.py        # ABC — provider contract
│   │   ├── gemini_provider.py      # Google Gemini (gemini-3-flash default)
│   │   ├── ollama_provider.py      # Local Ollama / llama3
│   │   └── openrouter_provider.py  # OpenRouter free tier
│   ├── profile_inputs/             # NEW — pluggable profile parsers
│   │   ├── base_profile_input.py   # ABC — profile-input contract
│   │   └── text_input.py           # Built-in: plain text (v1)
│   ├── auth/
│   │   ├── auth_strategy.py         # NEW — ordered oauth→api_key resolver
│   │   ├── google_oauth.py          # OAuth 2.0 device flow + keyring
│   │   └── session_store.py         # Playwright storage_state
│   ├── ai_engine.py                 # Facade: generate + score
│   ├── output.py                    # NEW (explicit) — CSV/JSON exporter
│   └── runner.py                    # Plugin loader + pipeline orchestrator
├── connectors/                       # USER DROP ZONE — new connectors
├── ai_providers/                     # USER DROP ZONE — new providers
├── profile_inputs/                   # USER DROP ZONE — new profile parsers (e.g. pdf, docx, image)
├── ui/
│   ├── cli/
│   │   └── cli.py                   # Click + Rich CLI
│   └── desktop/
│       ├── src-tauri/               # Rust/Tauri v2 shell + IPC
│       └── src/                     # Vue 3 + Vite frontend
│           ├── views/               # CriteriaView, ResultsView, SettingsView
│           └── components/          # JobCard, ProviderBadge, KeywordChip
├── fixtures/
│   └── jobs.json                    # Mock connector data
├── output/                           # Generated results (git-ignored)
└── config.yaml                      # User configuration
```

### 2.1 Plugin Drop Zones

The directories `connectors/`, `ai_providers/`, and `profile_inputs/` at the project root are
user-facing plugin zones. Files placed here are discovered and loaded identically to built-in plugins.
The loading mechanism in `runner.py` uses `importlib.util.spec_from_file_location` and inspects every
class in the module for subclasses of `BaseConnector`, `BaseAIProvider`, or `BaseProfileInput`.

> **RULE** — A drop-in file must define exactly one class inheriting the relevant base class. The class
> name is used as the plugin's display name in logs and UI.

---

## 3. Data Models

### 3.1 Job

Defined in `core/models/job.py`. All fields except `id`, `title`, `company`, `url` are optional —
connectors populate what they can.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | str | Required | UUID generated by connector |
| title | str | Required | Job title as posted |
| company | str | Required | Hiring company name |
| url | str | Required | Direct link to job posting |
| location | str \| None | Optional | Location string (city, remote, hybrid) |
| description | str \| None | Optional | Full or truncated job description |
| salary_range | str \| None | Optional | Salary string as posted |
| posted_date | datetime \| None | Optional | Date/time of posting |
| source | str | Required | Connector name (e.g. 'linkedin', 'indeed') |
| score | int \| None | Optional | AI score 0-100, set by ai_engine |
| match_reason | str \| None | Optional | AI explanation of the score |
| red_flags | list[str] | Optional | List of AI-identified concerns |
| raw | dict \| None | Optional | Original scraped payload, for debugging |

### 3.2 SearchCriteria

Defined in `core/models/search_criteria.py`. Generated by AI or filled manually by the user.

| Field | Type / Default | Description |
|-------|----------------|-------------|
| titles | list[str] | Target job titles |
| keywords | list[str] | Skills and technologies |
| exclude_keywords | list[str] | Terms that disqualify a listing |
| seniority_levels | list[str] | e.g. ['senior', 'lead', 'staff', 'principal'] |
| locations | list[str] | Allowed locations |
| min_score_threshold | int | **Effective** filter: jobs below this score are hidden. Seeded from `ai.min_score` (default 40); see §9 |
| max_results | int | Cap per connector (default: 50) |
| date_posted_days | int \| None | Only include jobs posted within N days (None = no filter) |
| raw_profile | str \| None | Original profile text used to generate these criteria |

### 3.3 Profile Input (new)

The profile a user provides is normalised to plain text by a **Profile Input plugin** before it reaches
`GENERATE_CRITERIA`. This keeps the AI engine input-format-agnostic and lets new formats be added as
drop-ins. v1 ships only `TextProfileInput` (passes typed text through). Future drop-ins (PDF, Word,
image-with-OCR or multimodal extraction) live in `profile_inputs/`. See the contract in §5.3.

---

## 4. Plugin Contracts (Abstract Base Classes)

### 4.1 BaseConnector

Defined in `core/connectors/base_connector.py`. All connector plugins must inherit this class.

```python
from abc import ABC, abstractmethod
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

class BaseConnector(ABC):
    name: str = 'unnamed'                 # Display name, override in subclass
    auth_methods: tuple[str, ...] = ('none',)  # ordered: e.g. ('oauth', 'session', 'none')
    enabled: bool = True

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> list[Job]:
        """Execute search and return raw (unscored) Job list."""

    async def authenticate(self) -> bool:
        """Optional: called before search() if auth is required. The runner resolves
        auth_methods in order (see §8). Return True if auth succeeded, False to skip."""
        return True
```

> **DEV NOTE** — `authenticate()` is called automatically by the runner before `search()`. Connectors
> whose `auth_methods` is `['none']` can skip implementing it; the default returns True. (v1.1 replaces
> the old single `auth_type` string with the ordered `auth_methods` list; `'none'`, `'session'`,
> `'oauth'`, `'api_key'` are the recognised values.)

### 4.2 BaseAIProvider

Defined in `core/ai_providers/base_provider.py`. All AI provider plugins must inherit this class.

```python
from abc import ABC, abstractmethod
from core.models.job import Job
from core.models.search_criteria import SearchCriteria

class BaseAIProvider(ABC):
    name: str = 'unnamed'
    auth_methods: tuple[str, ...] = ('api_key',)  # ordered: e.g. ('oauth', 'api_key')
    supports_local: bool = False

    @abstractmethod
    async def generate_criteria(self, profile: str) -> SearchCriteria:
        """Convert a plain-text profile/CV into a SearchCriteria object."""

    @abstractmethod
    async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
        """Score each job 0-100. Returns jobs with score, match_reason, and red_flags
        populated. Input jobs are not mutated."""

    async def initialize(self) -> None:
        """Optional: called once on startup (auth token refresh, health check, etc.)"""
        pass
```

> **Auth abstraction (v1.1)** — `auth_methods` declares, in priority order, how the plugin can
> authenticate. The runner's auth resolver (§8) tries each in turn: prefer OAuth where the user has it
> configured, fall back to an API key, and treat `'none'`/`supports_local` providers as always
> authenticated. This is the single mechanism for both connectors and providers.

---

## 5. Core Components

### 5.1 runner.py — Plugin Loader & Pipeline Orchestrator

On startup the runner scans the built-in directories and the user drop zones, dynamically loads all
valid plugins (connectors, providers, profile inputs), and executes the full pipeline on demand.

**Plugin Discovery Algorithm**

```python
def discover_plugins(directory: Path, base_class: type) -> list[type]:
    plugins = []
    for py_file in directory.glob('*.py'):
        if py_file.name.startswith('_') or py_file.name.startswith('base_'):
            continue
        spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, base_class) and obj is not base_class:
                plugins.append(obj)
    return plugins
```

**Pipeline Execution**

| Step | Description |
|------|-------------|
| 1. Load plugins | Discover all connectors, providers, and profile inputs from built-in + user dirs |
| 2. Validate config | Pydantic validates `config.yaml`; missing required fields raise clear errors |
| 3. Init AI provider | Instantiate configured provider, resolve auth (§8), call `initialize()` |
| 4. Parse profile | Active profile-input plugin normalises the supplied profile to text |
| 5. Generate criteria | `ai_engine.generate_criteria(profile_text)` → `SearchCriteria` |
| 6. Authenticate connectors | Resolve `auth_methods` for each enabled connector that needs auth |
| 7. Search (parallel) | `asyncio.gather()` all enabled `connector.search(criteria)` calls |
| 8. Merge results | Flatten, deduplicate by URL, tag source connector |
| 9. Score jobs | `ai_engine.score_jobs()` in batches of `config.ai.batch_size` (default 15) |
| 10. Sort and filter | Sort by score desc, filter out jobs below `min_score_threshold` |
| 11. Export | `core/output.py` writes CSV and/or JSON per `config.output.format` |

### 5.2 ai_engine.py — AI Facade

Wraps the active provider and exposes two clean async methods. Handles batching, prompt construction,
response parsing, and error recovery.

**GENERATE_CRITERIA prompt contract**

```
SYSTEM: You are a career advisor. Given a professional profile, extract a
        structured job search criteria object. Respond ONLY with valid JSON.
        Schema: { titles: [], keywords: [], exclude_keywords: [],
        seniority_levels: [], locations: [] }
USER: [profile_text]
```

**SCORE_JOBS prompt contract**

```
SYSTEM: You are a job match evaluator. Score each job 0-100 against the
        criteria. Respond ONLY with a JSON array. Each element:
        { id, score, match_reason, red_flags[] }
USER: CRITERIA: [json criteria]
      JOBS: [json array of Job objects, id+title+company+description only]
```

> **IMPORTANT** — The engine strips all fields except `id`, `title`, `company`, and `description`
> before sending to the AI provider. This minimises token usage and avoids sending sensitive data
> (e.g. raw scraped HTML) to external APIs.

### 5.3 Profile Input layer (new)

Defined in `core/profile_inputs/base_profile_input.py`. Normalises any supported profile source to
plain text for the AI engine.

```python
from abc import ABC, abstractmethod

class BaseProfileInput(ABC):
    name: str = 'unnamed'
    accepts: tuple[str, ...] = ('text',)   # e.g. ('text',), ('pdf',), ('png','jpg'), ('docx',)

    @abstractmethod
    async def to_text(self, source) -> str:
        """Return plain profile text. `source` is raw text (v1) or a file path (future)."""
```

v1 ships `TextProfileInput(accepts=('text',))`. PDF/Word/image parsers are added by dropping a file into
`profile_inputs/` — image parsers may either run local OCR or defer to a multimodal provider; that
choice is internal to the plugin and does not affect the engine.

### 5.4 output.py — Exporter (now explicit)

Writes scored results to `output/` as timestamped `results_<YYYY-MM-DD_HHMMSS>.csv` and/or `.json`
per `config.output.format`, using pandas. Previously implied by deliverable D-09 but absent from the
v1.0 tree; v1.1 gives it an explicit home at `core/output.py`.

---

## 6. Connector Specifications

### 6.1 Indeed Connector

| Property | Value |
|----------|-------|
| Class name | IndeedConnector |
| auth_methods | ['none'] |
| HTTP library | httpx (async, http/2) |
| Pagination | Query param `start=0,10,20…` up to max_results |
| Data extraction | Reverse-engineered embedded JSON (`window._initialData`) on result page |
| Rate limiting | Random 2-4 second delay between pages |
| Base URL template | `https://www.indeed.com/jobs?q={keywords}&l={location}&start={offset}` |
| Error handling | `httpx.TimeoutException` → log + return partial results |
| Max results | `config.connectors.indeed.max_results` (default 50) |

> **DEV NOTE** — Indeed embeds job data as a JSON blob in a `<script>` tag. Extract `window._initialData`
> via regex and parse as JSON. Fields: `jobTitle`, `companyName`, `jobLocationCity`,
> `jobLocationState`, `salaryMin`, `salaryMax`, `descriptionSnippet`.

### 6.2 LinkedIn Connector

| Property | Value |
|----------|-------|
| Class name | LinkedInConnector |
| auth_methods | ['session'] |
| Browser | Playwright Chromium (async) |
| Login flow | Visible browser (headless=False) on first run; `storage_state` saved after login |
| Subsequent runs | headless=True, `storage_state` loaded from encrypted file |
| Search URL | `https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}&f_TPR=r86400` |
| Pagination | Scroll-triggered infinite scroll; click 'See more jobs' up to N times |
| Data extraction | DOM job cards: `.job-card-container__link`, `.job-card-container__company-name` |
| Anti-detection | Random delays 1500-4000ms, human-like scroll, realistic User-Agent |
| Session file | `~/.jobhunter/sessions/linkedin.enc` (encrypted via session_store.py) |
| Max results | `config.connectors.linkedin.max_results` (default 50) |

> **SECURITY** — The LinkedIn session file contains authentication cookies. It is encrypted at rest
> using Fernet with a key derived from the machine ID, stored in the OS keyring (Windows Credential
> Manager / Linux Secret Service).

### 6.3 Mock Connector

| Property | Value |
|----------|-------|
| Class name | MockConnector |
| auth_methods | ['none'] |
| Purpose | Offline development and unit testing |
| Data source | `fixtures/jobs.json` — static array of Job objects |
| Filtering | Naive keyword match against title and description |
| Configurable | `fixture_path` override in `config.connectors.mock.fixture_path` |

---

## 7. AI Provider Specifications

### 7.1 Gemini Provider

| Property | Value |
|----------|-------|
| Class name | GeminiProvider |
| Model | `gemini-3-flash` (default as of 2026; `gemini-2.5-flash` / `-flash-lite` still selectable) |
| auth_methods | ['oauth', 'api_key'] |
| API key type | Restricted **authorization key** (AI Studio). Unrestricted standard keys are being rejected through 2026 and must not be used |
| OAuth | Google OAuth 2.0 Device Authorization Grant (preferred where the user has configured it) |
| Token storage | OS keyring: service=jobhunter |
| Free tier | ~1,500 requests/day, 1M TPM (Flash family) — sufficient for daily personal use |
| API endpoint | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` |
| Required env | `GEMINI_API_KEY` (api_key path); `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (oauth path) |

> The provider declares `auth_methods = ['oauth', 'api_key']`; the runner prefers OAuth when client
> credentials are present, otherwise uses the authorization API key. Both resolve to a valid bearer for
> the generateContent call.

**OAuth Device Flow Sequence**

| Step | Description |
|------|-------------|
| 1 | Provider calls Google's device auth endpoint with client_id and scope |
| 2 | Google returns device_code, user_code, verification_url |
| 3 | Provider opens verification_url in default browser |
| 4 | User sees user_code and approves in browser |
| 5 | Provider polls token endpoint every 5s (max 5 min) |
| 6 | On approval, Google returns access_token + refresh_token |
| 7 | Tokens stored in OS keyring; refresh token used silently on later runs |

### 7.2 Ollama Provider (Local / Testing)

| Property | Value |
|----------|-------|
| Class name | OllamaProvider |
| Model | `llama3` (default; any Ollama model) |
| auth_methods | ['none'] (local HTTP only) |
| Endpoint | `http://localhost:11434/api/generate` |
| Prerequisite | `ollama serve` + `ollama pull llama3` |
| Performance | Slow on non-GPU machines; dev/testing only |

### 7.3 OpenRouter Provider (Phase 2)

| Property | Value |
|----------|-------|
| Class name | OpenRouterProvider |
| Default model | `qwen/qwen3-coder:free` |
| Fallback model | `deepseek/deepseek-r1:free` (v1.0's `deepseek-v4-flash:free` removed from free tier) |
| auth_methods | ['api_key'] |
| Env var | `OPENROUTER_API_KEY` |
| Endpoint | `https://openrouter.ai/api/v1/chat/completions` (OpenAI-compatible) |
| Free tier | Rate-limited (≈20 req/min; daily cap varies). No credit card; account only |

> **NOTE** — OpenRouter free model slugs rotate. The `:free` suffix is required, and the exact IDs above
> should be re-verified at implementation time against `https://openrouter.ai/models?q=free`.

---

## 8. Authentication System

### 8.1 auth_strategy.py (new) — ordered resolver

A single resolver consumes a plugin's ordered `auth_methods` and returns a ready credential/None:

| Method value | Resolution |
|--------------|------------|
| `oauth` | Use `google_oauth.py` (or provider-specific OAuth) if client creds present; else skip to next |
| `api_key` | Read the configured env var (e.g. `GEMINI_API_KEY`, `OPENROUTER_API_KEY`); skip if unset |
| `session` | Load Playwright `storage_state` via `session_store.py` (LinkedIn); trigger login if missing |
| `none` | Always authenticated |

The first method that succeeds wins. If none succeed and the plugin requires auth, the runner logs a
clear message and skips that plugin (fail-graceful).

### 8.2 google_oauth.py

Implements the OAuth 2.0 Device Authorization Grant — optimal for desktop apps (no redirect-URI server).

| Method | Description |
|--------|-------------|
| get_token() | Returns a valid access token; checks keyring, refreshes if expired, triggers device flow if missing |
| _device_flow() | Initiates device auth, polls for token, stores result in keyring |
| _refresh_token() | Uses stored refresh_token to obtain a new access_token silently |
| revoke() | Deletes tokens from keyring (`jobhunter auth logout google`) |
| is_authenticated() | True if a valid (non-expired) token exists |

### 8.3 session_store.py

Manages Playwright `storage_state` files for session-based connectors, encrypted at rest with Fernet.

| Method | Description |
|--------|-------------|
| save(name, state_dict) | Encrypts and writes to `~/.jobhunter/sessions/{name}.enc` |
| load(name) | Reads and decrypts, returns dict for the Playwright context |
| exists(name) | True if an encrypted session file exists |
| delete(name) | Removes the file (`jobhunter auth logout linkedin`) |
| _get_key() | Derives a key from machine ID via PBKDF2HMAC, stored in OS keyring |

> **SECURITY** — The encryption key is derived from the machine's hardware UUID using PBKDF2HMAC/SHA-256
> and stored in the OS keyring. Session files are intentionally not portable between machines.

> **RULE** — `config.yaml` never contains credentials directly. The `auth.*` fields point to environment
> variable NAMES; actual values are read at runtime. Enforced by a pydantic validator.

---

## 9. Configuration System

### 9.1 config.yaml structure

```yaml
ai:
  provider: gemini             # gemini | ollama | openrouter
  model: gemini-3-flash        # model id within the provider
  batch_size: 15               # jobs per AI scoring call
  min_score: 40                # DEFAULT seed for SearchCriteria.min_score_threshold (see below)
profile:
  input: text                  # active profile-input plugin (text | pdf | docx | image …)
connectors:
  linkedin:
    enabled: true
    max_results: 50
    delay_min: 1.5
    delay_max: 4.0
  indeed:
    enabled: true
    max_results: 50
    delay_min: 2.0
    delay_max: 5.0
  mock:
    enabled: false
    fixture_path: fixtures/jobs.json
output:
  format: both                 # csv | json | both
  directory: output/
auth:
  google_client_id_env: GOOGLE_CLIENT_ID
  google_client_secret_env: GOOGLE_CLIENT_SECRET
  gemini_api_key_env: GEMINI_API_KEY
  openrouter_api_key_env: OPENROUTER_API_KEY
  adzuna_app_id_env: ADZUNA_APP_ID
  adzuna_app_key_env: ADZUNA_APP_KEY
```

> **Filter precedence (v1.1)** — `SearchCriteria.min_score_threshold` is the single effective filter
> applied at pipeline step 10. `ai.min_score` only supplies its **default** when criteria are generated;
> if the user edits the threshold on the criteria (CLI/UI), that value wins. This removes the v1.0
> ambiguity of two independent knobs.

### 9.2 Environment Variable Override

Any `config.yaml` field can be overridden via env var using double-underscore notation:

```
AI__PROVIDER=ollama                    # overrides ai.provider
CONNECTORS__LINKEDIN__ENABLED=false    # overrides connectors.linkedin.enabled
AI__BATCH_SIZE=20                      # overrides ai.batch_size
```

---

## 10. CLI Interface

### 10.1 Command Structure

| Command | Description |
|---------|-------------|
| jobhunter run | Run full pipeline (generate + search + score + export) |
| jobhunter run --profile <file> | Load profile from file (routed through the matching profile-input plugin) |
| jobhunter run --provider ollama | Override AI provider for this run only |
| jobhunter run --no-generate | Skip criteria generation; use last saved criteria |
| jobhunter run --refine | Multi-turn: amend the last criteria interactively, then re-run |
| jobhunter auth google | Trigger Google OAuth device flow and save token |
| jobhunter auth linkedin | Open Playwright browser for manual LinkedIn login |
| jobhunter auth logout <service> | Revoke and delete stored credentials |
| jobhunter auth status | Show auth status for all services |
| jobhunter config show | Print resolved config (secrets redacted) |
| jobhunter config set <key> <value> | Update a config value |
| jobhunter connectors list | Show all loaded connectors and status |
| jobhunter providers list | Show all loaded AI providers |
| jobhunter export --format csv | Re-export last results in specified format |

### 10.2 CLI Output Example

```
JobHunter v1.1  |  Provider: Gemini 3 Flash  |  Connectors: 2
[1/4] Generating search criteria from profile...
      Titles: Senior .NET Dev, DevOps Lead, Squad Lead
      Keywords: C#, Kubernetes, GCP, CI/CD, Azure DevOps
[2/4] Searching LinkedIn...                   [done] 47 jobs
[2/4] Searching Indeed...                     [done] 38 jobs
[3/4] Scoring 85 jobs (6 batches)...          [done]
[4/4] Exporting results...
      output/results_2026-06-17_143022.csv
      output/results_2026-06-17_143022.json
┌─────────┬────────────────────────────┬─────────────────┐
│  Score  │ Title                      │ Company         │
├─────────┼────────────────────────────┼─────────────────┤
│   94    │ Senior DevOps Lead         │ Accenture Egypt │
│   91    │ .NET Squad Lead            │ Vodafone Egypt  │
│   88    │ Cloud Engineer (GCP)       │ IBM Egypt       │
└─────────┴────────────────────────────┴─────────────────┘
```

---

## 11. Desktop UI (Tauri + Vue 3)

### 11.1 Tauri-Python IPC Architecture

The Python core is invoked as a Tauri sidecar subprocess. The Rust backend spawns the Python CLI as a
child process and communicates via JSON over stdin/stdout pipes — avoiding a REST server and keeping the
Python core portable.

```jsonc
// Request (Rust → Python stdin)
{ "command": "run_pipeline", "args": { "profile": "...", "provider": "gemini" } }
// Progress event (Python stdout, streaming)
{ "type": "progress", "step": "scoring", "current": 3, "total": 6 }
// Final result (Python stdout)
{ "type": "result", "data": [ { /* Job fields including score */ } ] }
```

| Layer | Responsibility |
|-------|----------------|
| UI Event | Vue component emits IPC event via Tauri `invoke()` |
| Tauri command | Rust handler receives the command, serialises args to JSON |
| IPC call | Rust writes JSON to Python sidecar stdin |
| Python response | Python writes `{ status, data }` or `{ status, error }` to stdout |
| Result delivery | Rust reads stdout, deserialises, emits back to Vue |
| Streaming | Long operations emit progress events every batch |

### 11.2 View Specifications

**Criteria View** — Profile text area (one-shot input), **Generate with AI** button, editable keyword
chips / seniority checkboxes / location tags, **Run Search**, **Save Criteria**. v1.1 adds a
**Refine** affordance: after generation the user can amend criteria conversationally (multi-turn) before
running. File upload (PDF/Word/image) is shown as a future-enabled control backed by profile-input plugins.

**Results View** — Sortable table (Score, Title, Company, Location, Source, Date), color-coded score
badges (green 80-100, amber 60-79, orange 40-59, gray <40 hidden), row-click detail panel
(description, match_reason, red_flags, link), filter bar, export, re-run (merges new results).

**Settings View** — AI provider selector, API key field (saved to env/secure store, not config),
OAuth connect button, connector toggles, max-results and delay sliders, auth status panel, LinkedIn
auth button.

---

## 12. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit: AI Engine | Prompt generation, response parsing, score assignment (mocked provider) |
| Unit: Plugin Loader | Discovery/loading/instantiation of connectors, providers, **profile inputs** from temp dirs |
| Unit: Data Models | `Job` and `SearchCriteria` pydantic validation |
| Unit: Auth | Token refresh, **auth_strategy resolution order**, session encrypt/decrypt round-trips (no real OAuth) |
| Unit: Profile Input | `TextProfileInput.to_text` round-trip; contract test for the base class |
| Contract: Connector | Each connector returns `list[Job]` with all required fields non-null |
| Integration: Pipeline | Full run with MockConnector + OllamaProvider (local, no network) |
| E2E: CLI | `jobhunter run` with fixtures asserts CSV output exists and contains scored rows |

**Connector contract test**

```python
# tests/contracts/test_connector_contract.py
@pytest.mark.parametrize('connector_class', discover_all_connectors())
async def test_connector_returns_valid_jobs(connector_class):
    connector = connector_class()
    criteria = SearchCriteria(titles=['Software Engineer'],
                              keywords=['Python'], locations=['Remote'])
    jobs = await connector.search(criteria)
    assert isinstance(jobs, list)
    for job in jobs:
        assert job.id and job.title and job.company and job.url
        assert job.source == connector.name
```

---

## 13. Build & Deployment

### 13.1 Development Setup

| Step | Command |
|------|---------|
| 1. Python env | `python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt` |
| 2. Playwright | `playwright install chromium --with-deps` |
| 3. Node deps | `cd ui/desktop && npm install` |
| 4. Rust | `rustup update stable` |
| 5. Tauri dev | `npm run tauri dev` (spawns Python sidecar) |
| 6. CLI only | `python -m ui.cli.cli run` |
| 7. Tests | `pytest tests/ -v --asyncio-mode=auto` |

### 13.2 Windows Installer Build

| Component | Notes |
|-----------|-------|
| Python bundle | PyInstaller packages core + deps into a single sidecar executable |
| Tauri build | `npm run tauri build` → `.msi` in `ui/desktop/src-tauri/target/release/bundle/msi/` |
| Bundle size target | < 120 MB |
| Signing | Windows code-signing certificate for distribution (tauri.conf.json) |
| Auto-update | Tauri v2 built-in updater |

### 13.3 Python Sidecar Packaging

```python
# pyinstaller jobhunter_core.spec --clean
a = Analysis(['ui/cli/cli.py'], ...,
  hiddenimports=['playwright', 'httpx', 'google.generativeai'],
  datas=[('fixtures/', 'fixtures/'), ('config.yaml', '.')])
```

### 13.4 Version control

Local git over the whole project folder (docs + code). `output/` is git-ignored. Remote (Bitbucket /
GitHub) deferred — initialise locally for history and progress tracking.

---

## 14. Extension Guides

### 14.1 Adding a New Job Connector

```python
# 1. Create file: connectors/wuzzuf.py
from core.connectors.base_connector import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
import httpx, uuid

class WuzzufConnector(BaseConnector):
    name = 'wuzzuf'
    auth_methods = ['none']
    async def search(self, criteria: SearchCriteria) -> list[Job]:
        jobs = []
        async with httpx.AsyncClient() as client:
            resp = await client.get('https://wuzzuf.net/search/jobs/',
                params={'q': ' '.join(criteria.keywords)})
            # ... parse response ...
            jobs.append(Job(id=str(uuid.uuid4()), title='...', company='...',
                            url='...', source=self.name))
        return jobs
# 2. Drop the file into connectors/
# 3. Enable in config.yaml under connectors.wuzzuf.enabled: true
# 4. Auto-discovered on next run.
```

### 14.2 Adding a New AI Provider

```python
# 1. Create file: ai_providers/groq_provider.py
from core.ai_providers.base_provider import BaseAIProvider
import httpx, json, os

class GroqProvider(BaseAIProvider):
    name = 'groq'
    auth_methods = ['api_key']
    async def generate_criteria(self, profile): ...
    async def score_jobs(self, jobs, criteria): ...
    async def _call(self, prompt: str) -> str:
        async with httpx.AsyncClient() as c:
            r = await c.post('https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {os.environ["GROQ_API_KEY"]}'},
                json={'model': 'llama3-8b-8192',
                      'messages': [{'role': 'user', 'content': prompt}]})
            return r.json()['choices'][0]['message']['content']
# 2. Set ai.provider: groq ; 3. Set env GROQ_API_KEY
```

### 14.3 Adding a New Profile Input parser (new)

```python
# 1. Create file: profile_inputs/pdf_input.py
from core.profile_inputs.base_profile_input import BaseProfileInput

class PdfProfileInput(BaseProfileInput):
    name = 'pdf'
    accepts = ('pdf',)
    async def to_text(self, source) -> str:
        # extract text layer; OCR or multimodal fallback for scanned PDFs
        ...
# 2. Drop into profile_inputs/ ; 3. Set profile.input: pdf
```

---

## 15. Open Items & Future Phases

| ID | Feature | Description |
|----|---------|-------------|
| OI-01 | Scheduled runs | Windows Task Scheduler integration for a daily cron, append results |
| OI-02 | Notifications | Windows toast when new high-score jobs are found |
| OI-03 | Regional connectors | Wuzzuf, Bayt.com, Naukri, GulfTalent (Phase 3) |
| OI-04 | Apply integration | One-click Apply for LinkedIn Easy Apply (requires consent flow) |
| OI-05 | Profile versioning | Multiple profile/criteria presets |
| OI-06 | Team mode | Shared criteria config in a team Notion or Git repo |
| OI-07 | Result deduplication | Cross-connector dedup by title+company fuzzy match, not just URL |
| OI-08 | Profile-input add-ons | PDF / Word / image (OCR or multimodal) profile parsers as drop-ins |

---

*End of Software Design Document — v1.1*
*Prepared by: Abdelrahman — Squad 3 Lead, Dsquares | June 2026*
