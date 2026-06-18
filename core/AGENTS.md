# core — JobHunter Python core (engine, models, plugins, infra)

The importable heart of the app: data models, plugin contracts + built-ins, the AI engine, auth, the
pipeline runner, and shared infra. Pure logic stays side-effect-free; I/O lives in thin adapters
(ADR-008, dev plan §5).

## Contents (filled chunk by chunk)
- `config.py` — config models + YAML loader + env overrides + no-secrets validator. **[C-003 · present]**
- `logging.py` — structured JSON logger. **[C-002 · present]**
- `models/` — `Job`, `SearchCriteria` (see `models/AGENTS.md`). **[C-004 · present]**
- `connectors/`, `ai_providers/`, `profile_inputs/`, `auth/`, `ai_engine/` — empty stubs until their chunks land.

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

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md) · Spec: `../Documents/JobHunter_SDD_v1.1.md` · Logging std: dev plan §6.
