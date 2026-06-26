# ui/cli - Click/Rich command interface

## Contents
- `cli.py` - `jobhunter run` (real `core.runner` pipeline + Rich render, C-026) and command groups.
- `auth.py` - C-027 `auth status/logout` commands for API-key and session-backed auth.
- `config_cmd.py` - C-028 `config show`, plugin list, and result re-export commands.
- `sidecar.py` - C-031 Tauri desktop sidecar entrypoint; run with `python -m ui.cli.sidecar`.
- `__init__.py` - package marker.

## Contracts
- CLI commands may write human output to stdout. Core modules must not.
- Keep command handlers thin: parse options, call core functions, render results.
- `run` drives the real `core.runner` pipeline (C-026); progress events go to stderr so stdout stays the table.
- `sidecar` is the IPC entrypoint for the Tauri desktop shell: reads one JSON request from stdin
  (`run_pipeline`, `generate_criteria`, or `export_results`), emits protocol JSON to stdout, and logs
  to stderr only. **Stdout is the IPC channel - no stray log lines.**
- `auth status` reports env-var/session presence without printing credential values; OAuth/browser login
  commands stay deferred to their provider/connector chunks.
- Error paths in both `cli.py` and `sidecar.py` redact credential values before surfacing them (stdout
  table / IPC). Redaction resolves env-var *names* from the loaded `config.auth` (so a renamed env var is
  still caught) plus the built-in `AuthConfig()` defaults, and replaces values **longest-first** so a
  secret that is a substring of another leaves no fragment exposed (C-071).
- `export --format` re-exports the newest `results_*.json` file from the configured output directory;
  desktop `export_results` uses the same configured exporter for in-memory result rows.

## Pointers
- Parent: [../../AGENTS.md](../../AGENTS.md)
- Desktop shell: [../../ui/desktop/AGENTS.md](../../ui/desktop/AGENTS.md)
- Dev plan: `Documents/JobHunter_DEV_PLAN_v1.0.md` C-026, C-027, C-028, C-031, and C-050.
