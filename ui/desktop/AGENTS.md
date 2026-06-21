# ui/desktop - Tauri v2 desktop shell + Vue frontend

## Contents

- `src/index.html` - Vite HTML entry that mounts the Vue application.
- `src/main.ts` - Vue 3 entry point; installs Pinia + router and imports design tokens.
- `src/App.vue` - Desktop app shell with left navigation, header state, and theme toggle.
- `src/router/index.ts` - Hash-router routes for Criteria, Results, and Settings views.
- `src/stores/pipeline.ts` - Pinia pipeline store; invokes `run_pipeline` and records
  `pipeline-progress` IPC events.
- `src/views/CriteriaView.vue` - Criteria workspace: profile input, local draft generation/editing,
  refine, localStorage save/load, and Run Search through the existing pipeline IPC.
- `src/views/ResultsView.vue` - Results workspace: score-band table, sorting/filtering, below-40 hide
  rule, row detail drawer, JSON export, and re-run merge over the pipeline store results.
- `src/views/SettingsView.vue` - Settings workspace: provider selection, connector toggles, search
  limits, masked API-key save affordance, auth status, and disabled deferred auth actions.
- `src/styles/app.css` - Token-backed shell/component styling.
- `src-tauri/src/main.rs` - Tauri entry point (thin wrapper calling `lib::run()`).
- `src-tauri/src/lib.rs` - `run_pipeline` Tauri command + `find_python` / `project_root_from_env`
  helpers; `run()` wires the Tauri builder.
- `src-tauri/tests/ipc_integration.rs` - Rust integration test that spawns the Python sidecar
  and asserts the full stdin/stdout IPC round-trip works (progress events + result).
- `src-tauri/Cargo.toml` - Tauri v2 + serde_json + tempfile (dev).
- `src-tauri/build.rs` - `tauri_build::build()` build script.
- `src-tauri/tauri.conf.json` - Tauri v2 app config (identifier, window, bundle, Vite build hooks).
- `src-tauri/capabilities/default.json` - Tauri v2 capability grant for the main window.
- `src-tauri/icons/icon.ico` - Placeholder application icon (required by tauri-build).
- `package.json` - npm scripts: `dev`, `build`, `test`, `tauri`, `tauri:dev`, `tauri:build`.

## IPC Contract

Rust -> Python stdin, one JSON line:

```json
{"command": "run_pipeline", "args": {"profile": "...", "provider": "ollama"}}
```

Python stdout is newline-delimited JSON, streaming:

```json
{"type":"progress","run_id":"...","stage":"search","state":"active","current":3,"total":6}
```

Then a final line:

```json
{"type":"result","data":[{...job fields including score...}]}
```

Critical rule: only protocol JSON goes to stdout; all Python logs go to stderr. A stray stdout log
corrupts the stream.

## Python Sidecar

Module: `ui/cli/sidecar.py` (also see [`ui/cli/AGENTS.md`](../../ui/cli/AGENTS.md)).

```bash
python -m ui.cli.sidecar
```

The Tauri command spawns this via `python -m ui.cli.sidecar` with:

- CWD = project root, where `config.yaml` lives.
- `PYTHONPATH` = project root, so `core` and `ui` are importable.
- stdin = the `run_pipeline` JSON request.
- stdout = progress events + final result, parsed by Rust.
- stderr = Python logs, inherited by the Tauri process and safe to ignore.

## Python Path Resolution

`find_python()` and `project_root_from_env()` in `lib.rs` resolve the Python executable:

1. `JOBHUNTER_PYTHON` env var, useful in tests and CI.
2. `.venv/Scripts/python.exe` relative to `JOBHUNTER_ROOT` or `CWD`.
3. `py`, `python3`, `python` in PATH.

Set `JOBHUNTER_ROOT` to the project root if running the Tauri app from a different CWD.

## Build Prerequisites

Tauri v2 on Windows requires the MSVC toolchain. Before running `cargo build`, `cargo test`, or
`npm run tauri build`, initialise the MSVC environment:

```bat
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
```

Or launch from a Visual Studio 2022 Developer Command Prompt.

Application Control note: if `npm run tauri build` release builds are blocked by Windows WDAC policy,
use `npm run tauri build -- --debug` for debug builds. The code is identical; only the optimisation
level differs.

## Conventions

- All Tauri commands are `async fn`; `pub` on a command function causes a Tauri 2.x macro name
  collision (`E0255`).
- Frontend events for streamed progress use the event name `pipeline-progress`.
- Frontend state lives in Pinia stores under `src/stores/`; keep event names aligned with Rust and the
  Python sidecar stdout contract.
- C-034 is frontend-only: Criteria draft generation/editing is local UI state; the only backend call is
  the existing `run_pipeline(profile, provider)` command.
- C-035 is frontend-only: Results rendering derives from `pipeline.results`; re-run uses
  `pipeline.lastRun` and merges fresh rows locally by result identity.
- C-036 is frontend-only until a Tauri settings command lands: non-secret settings persist to a
  local config-shaped payload, while API keys are cleared after save and represented only by saved
  status so secret values are never written to config.

## Pointers

- Parent: [`../../AGENTS.md`](../../AGENTS.md)
- Python sidecar: [`../cli/AGENTS.md`](../cli/AGENTS.md)
- SDD section 11.1 - Tauri/Python IPC architecture.
- DEV_PLAN section 9.3 - progress event data contract.
