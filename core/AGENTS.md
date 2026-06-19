# core — JobHunter Python core (engine, models, plugins, infra)

The importable heart of the app: data models, plugin contracts + built-ins, the AI engine, auth, the
pipeline runner, and shared infra. Pure logic stays side-effect-free; I/O lives in thin adapters
(ADR-008, dev plan §5).

## Contents (filled chunk by chunk)
- `config.py` — config models + YAML loader + env overrides + no-secrets validator. **[C-003 · present]**
- `logging.py` — structured JSON logger. **[C-002 · present]**
- `models/` — `Job`, `SearchCriteria` (see `models/AGENTS.md`). **[C-004 · present]**
- `connectors/` — `BaseConnector` ABC + built-in Mock connector (see `connectors/AGENTS.md`). **[C-005, C-018 · present]**
- `ai_providers/` — `BaseAIProvider` ABC + built-in Ollama provider (see `ai_providers/AGENTS.md`). **[C-006, C-015 · present]**
- `walking_skeleton.py` — C-039 stub profile -> criteria -> fixture search -> score -> JSON export.
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
  / OutputConfig / AuthConfig. All use `extra="forbid"` (unknown/secret keys fail load); `output.format` is a `csv|json|both` enum; `delay_min <= delay_max` (ADR-018).
- **Logging (`logging.py`, ADR-010 / dev plan §6).** `get_logger(name, **ctx)` → a `Logger`;
  `.bind(**ctx)` returns a **new** logger (immutable context); `.debug/.info/.warning/.error(msg,
  **fields)`. Output is **JSON lines to stderr only** — never stdout (it is the sidecar IPC channel).
  `new_run_id()` gives a per-run correlation id to thread via `bind(run_id=...)`. Secret-looking keys
  (token, api_key, password, authorization, cookie, …) are auto-redacted. Pure helpers: `format_record`,
  `redact`.
- **Walking skeleton (`walking_skeleton.py`, C-039).** This is deliberately temporary integration
  wiring, not the final runner/exporter/connector implementation. Keep it deterministic and side-effect
  free except for explicit fixture loading and JSON export.
- **Runner (`runner.py`, C-009).** Discovery is importlib-based and direct-directory only: skip `_*.py`
  and `base_*.py`, return plugin classes rather than instances, and keep orchestration for later chunks.
- **Mock connector (`connectors/mock_connector.py`, C-018).** `MockConnector` loads deterministic jobs
  from `fixtures/jobs.json` or an injected fixture path, forces `source = "mock"`, and filters by a
  case-insensitive keyword match against title/description.
- **Auth (`auth/auth_strategy.py`, C-008).** `resolve_auth()` consumes ordered plugin
  `auth_methods`, tries injected providers/env in order, returns `AuthResult` for the first success, and
  warns + returns `None` when required auth is unmet.
- **Session store (`auth/session_store.py`, C-019).** `SessionStore` encrypts Playwright
  `storage_state` dicts with Fernet, stores the derived key through keyring, and keeps session files in
  `~/.jobhunter/sessions/*.enc` by default.
- **AI engine prompts (`ai_engine/prompts.py`, C-010).** Prompt builders are deterministic and pure.
  Score prompts include structured criteria plus only job `id`, `title`, `company`, and `description`.
- **AI response parsing (`ai_engine/parsing.py`, C-011).** Parsers convert provider JSON into
  `SearchCriteria` or scored `Job` copies and return `None` for malformed/invalid provider output.
- **AI job scrubbing (`ai_engine/scrub.py`, C-012).** Scrub helpers keep only job `id`, `title`,
  `company`, and `description` before provider calls.
- **AI batching (`ai_engine/batching.py`, C-013).** `batch_items()` splits sequences into
  order-preserving batches for later scoring calls.
- **AI facade (`ai_engine/__init__.py`, C-014).** `AIEngine` wraps an injected async prompt provider,
  builds prompts, batches scoring calls, parses provider JSON, raises `AIEngineError` for unrecoverable
  output, and returns scored `Job` copies without mutating inputs.
- **Ollama provider (`ai_providers/ollama_provider.py`, C-015).** `OllamaProvider` calls local
  `http://localhost:11434/api/generate` with `stream: false`, default model `llama3`, no auth, and
  delegates prompt orchestration/parsing to `AIEngine`.
- **Pipeline transforms (`pipeline.py`, C-022).** `merge_results()`, `dedup_by_url()`,
  `sort_by_score()`, and `filter_below_threshold()` are pure helpers for runner steps 8-10; they do no
  config reads, logging, filesystem, or network work.
- **Progress events (`progress.py`, C-023).** `ProgressEmitter` writes validated progress protocol
  events to stdout and emits a matching INFO log to stderr; metric payloads are redacted before both
  writes.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md) · Spec: `../Documents/JobHunter_SDD_v1.1.md` · Logging std: dev plan §6.
