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
- `sidecar` is the IPC entrypoint for the Tauri desktop shell: reads one `run_pipeline` JSON request
  from stdin, emits progress events **and the final result** to stdout (reversed vs CLI), and logs to
  stderr only. **Stdout is the IPC channel — no stray log lines.**
- `auth status` reports env-var/session presence without printing credential values; OAuth/browser login
  commands stay deferred to their provider/connector chunks.
- `export --format` re-exports the newest `results_*.json` file from the configured output directory.

## Pointers
- Parent: [../../AGENTS.md](../../AGENTS.md)
- Desktop shell: [../../ui/desktop/AGENTS.md](../../ui/desktop/AGENTS.md)
- Dev plan: `Documents/JobHunter_DEV_PLAN_v1.0.md` C-026, C-027, C-028, C-031, and C-050.
