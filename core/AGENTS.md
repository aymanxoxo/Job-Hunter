# core — JobHunter Python core (engine, models, plugins, infra)

The importable heart of the app: data models, plugin contracts + built-ins, the AI engine, auth, the
pipeline runner, and shared infra. Pure logic stays side-effect-free; I/O lives in thin adapters
(ADR-008, dev plan §5).

## Contents (filled chunk by chunk)
- `config.py` — config models + YAML loader + env overrides + no-secrets validator. **[C-003 · present]**
- `logging.py` — structured JSON logger. **[C-002 · present]**
- `models/` — `Job`, `SearchCriteria` (see `models/AGENTS.md`). **[C-004 · present]**
- `connectors/` — `BaseConnector` ABC + built-in Mock and Adzuna connectors (see `connectors/AGENTS.md`). **[C-005, C-018, C-051 · present]**
- `ai_providers/` — `BaseAIProvider` ABC + built-in Ollama, OpenRouter & Gemini providers (see `ai_providers/AGENTS.md`). **[C-006, C-015, C-030, C-017 · present]**
- `pipeline.py` — pure merge/dedup/sort/filter transforms for runner pipeline results. **[C-022 · present]**
- `progress.py` — stdout protocol progress events with matching stderr logs. **[C-023 · present]**
- `profile_inputs/` — `BaseProfileInput` ABC + `TextProfileInput` (see `profile_inputs/AGENTS.md`). **[C-007 · present]**
- `runner.py` — plugin discovery helper for built-in and user drop-zone modules. **[C-009 · present]**
- `auth/` — ordered auth strategy resolver + encrypted session store (see `auth/AGENTS.md`). **[C-008, C-019 · present]**
- `ai_engine/` — AI facade plus pure prompt builders, response parsers, job scrubbing, and batching (see `ai_engine/AGENTS.md`). **[C-010–C-014 · present]**

## Conventions / contracts
- **Config (`config.py`, SDD §9).** `load_config(path, env=None)` → a validated `Config`;
  `apply_env_overrides` (pure) applies `KEY__SUBKEY` env overrides; `auth.*` fields must be env-var
  NAMES (a validator rejects pasted secrets). Sub-models: AIConfig / ProfileConfig / ConnectorSettings
  / OutputConfig / AuthConfig. All use `extra="forbid"` (unknown/secret keys fail load); `auth.*`
  fields are env-var names only, including Adzuna API keys; `output.format` is a `csv|json|both`
  enum; `delay_min <= delay_max` (ADR-018).
- **Logging (`logging.py`, ADR-010 / dev plan §6).** `get_logger(name, **ctx)` → a `Logger`;
  `.bind(**ctx)` returns a **new** logger (immutable context); `.debug/.info/.warning/.error(msg,
  **fields)`. Output is **JSON lines to stderr only** — never stdout (it is the sidecar IPC channel).
  `new_run_id()` gives a per-run correlation id to thread via `bind(run_id=...)`. Secret-looking keys
  (token, api_key, password, authorization, cookie, …) are auto-redacted. Pure helpers: `format_record`,
  `redact`.
- **Runner (`runner.py`, C-009/C-025).** Discovery is importlib-based and direct-directory only: skip
  `_*.py` and `base_*.py`, return plugin classes rather than instances. The `Runner` orchestrator wires
  profile → criteria → search → score → filter → export; search is fail-graceful per connector and emits
  connector-level progress sub-events (`done` with job counts, `failed`, `skipped`, and zero-result
  `done`) so the desktop can show partial success without marking the whole run failed. **Scoring is
  fail-graceful too (C-072):** if `score_jobs` raises, the run continues with the *unscored* jobs and
  skips the threshold filter so the listings stay visible instead of collapsing to an empty result;
  partial unscored jobs from a *successful* call are still filtered out (and logged). Auth-related
  constructor env-var names are supplied via each plugin class's `auth_config_kwargs(auth)` hook rather
  than runner-side plugin-name branching (C-075).
- **Mock connector (`connectors/mock_connector.py`, C-018).** `MockConnector` loads deterministic jobs
  from `fixtures/jobs.json` or an injected fixture path, forces `source = "mock"`, and filters by a
  case-insensitive whole-keyword match against title/description.
- **Adzuna connector (`connectors/adzuna_connector.py`, C-051).** `AdzunaConnector` calls the official
  jobs API with `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`, maps response records to raw unscored `Job` objects,
  and raises clear connector errors for missing credentials, HTTP failures, or malformed JSON.
- **Auth (`auth/auth_strategy.py`, C-008).** `resolve_auth()` consumes ordered plugin
  `auth_methods`, tries injected providers/env in order, returns `AuthResult` for the first success, and
  warns + returns `None` when required auth is unmet.
- **Session store (`auth/session_store.py`, C-019).** `SessionStore` encrypts Playwright
  `storage_state` dicts with Fernet, stores the derived key through keyring, and keeps session files in
  `~/.jobhunter/sessions/*.enc` by default.
- **AI engine prompts (`ai_engine/prompts.py`, C-010).** Prompt builders are deterministic and pure.
  Score prompts include structured criteria plus only job `id`, `title`, `company`, and `description`.
- **AI response parsing (`ai_engine/parsing.py`, C-011/C-064).** Parsers convert provider JSON into
  `SearchCriteria` or scored `Job` copies, return `None` for malformed top-level provider output, and
  skip malformed scored-job items so one bad row does not discard the rest of a batch.
- **AI job scrubbing (`ai_engine/scrub.py`, C-012/C-069).** Scrub helpers keep only job `id`, `title`,
  `company`, and `description` before provider calls, and neutralise prompt-injection in the untrusted
  description (`neutralize_prompt_text()` strips control chars + defangs role markers).
- **AI batching (`ai_engine/batching.py`, C-013).** `batch_items()` splits sequences into
  order-preserving batches for later scoring calls.
- **AI facade (`ai_engine/__init__.py`, C-014).** `AIEngine` wraps an injected async prompt provider,
  builds prompts, batches scoring calls, parses provider JSON, raises `AIEngineError` for unrecoverable
  output, and returns scored `Job` copies without mutating inputs.
- **Ollama provider (`ai_providers/ollama_provider.py`, C-015).** `OllamaProvider` calls local
  `http://localhost:11434/api/generate` with `stream: false`, default model `llama3`, no auth, and
  delegates prompt orchestration/parsing to `AIEngine`.
- **OpenRouter provider (`ai_providers/openrouter_provider.py`, C-030).** `OpenRouterProvider` posts
  OpenAI-style `chat/completions` with a `Bearer` key from `$OPENROUTER_API_KEY` (read at call time,
  never logged), default model `qwen/qwen3-coder:free` with a fallback model on error, and delegates
  to `AIEngine`.
- **Gemini provider (`ai_providers/gemini_provider.py`, C-017).** `GeminiProvider` calls Google's
  `generateContent`; auth resolves via `auth_strategy` (OAuth bearer when wired, else
  `x-goog-api-key` from `$GEMINI_API_KEY`); default model `gemini-3.5-flash`; delegates to `AIEngine`.
- **Pipeline transforms (`pipeline.py`, C-022).** `merge_results()`, `dedup_by_url()`,
  `sort_by_score()`, and `filter_below_threshold()` are pure helpers for runner steps 8-10; they do no
  config reads, logging, filesystem, or network work.
- **Progress events (`progress.py`, C-023/C-061).** `ProgressEmitter` writes validated progress protocol
  events to stdout and emits a matching INFO log to stderr; metric payloads are redacted before both
  writes. Search events may include a `connector` sub-row name; connector-scoped `failed` events are
  warnings, not whole-run failures.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md) · Spec: `../Documents/JobHunter_SDD_v1.1.md` · Logging std: dev plan §6.
