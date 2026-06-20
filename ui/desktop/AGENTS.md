# ui/desktop — Tauri v2 desktop shell + Python sidecar IPC

## Contents

- `src-tauri/src/main.rs` — Tauri entry point (thin wrapper calling `lib::run()`).
- `src-tauri/src/lib.rs` — `run_pipeline` Tauri command + `find_python` / `project_root_from_env`
  helpers; `run()` wires the Tauri builder.
- `src-tauri/tests/ipc_integration.rs` — Rust integration test that spawns the Python sidecar
  and asserts the full stdin/stdout IPC round-trip works (progress events + result).
- `src-tauri/Cargo.toml` — Tauri v2 + serde_json + tempfile (dev).
- `src-tauri/build.rs` — `tauri_build::build()` build script.
- `src-tauri/tauri.conf.json` — Tauri v2 app config (identifier, window, bundle).
- `src-tauri/capabilities/default.json` — Tauri v2 capability grant for the main window.
- `src-tauri/icons/icon.ico` — Placeholder application icon (required by tauri-build).
- `src/index.html` — Minimal placeholder frontend (Vue scaffold lands in C-032).
- `package.json` — npm scripts: `tauri`, `tauri:dev`, `tauri:build`.

## IPC contract (SDD §11.1 + DEV_PLAN §9.3)

**Rust → Python stdin** (one JSON line):
```json
{"command": "run_pipeline", "args": {"profile": "...", "provider": "ollama"}}
```

**Python stdout** (newline-delimited JSON, streaming):
```json
{"type":"progress","run_id":"...","stage":"search","state":"active","current":3,"total":6}
```
Then a final line:
```json
{"type":"result","data":[{...job fields including score...}]}
```

**Critical rule:** only protocol JSON goes to stdout; ALL Python logs go to stderr.
A stray stdout log corrupts the stream.

## Python sidecar entrypoint

Module: `ui/cli/sidecar.py` (also see [`ui/cli/AGENTS.md`](../../ui/cli/AGENTS.md)).

```bash
python -m ui.cli.sidecar       # from project root
```

The Tauri command spawns this via `python -m ui.cli.sidecar` with:
- **CWD** = project root (where `config.yaml` lives).
- **PYTHONPATH** = project root (so `core`, `ui` are importable).
- **stdin** = the `run_pipeline` JSON request.
- **stdout** = progress events + final result (parsed by Rust).
- **stderr** = Python logs (inherited by Tauri process, safe to ignore).

## Python path resolution

`find_python()` and `project_root_from_env()` in `lib.rs` resolve the Python executable:
1. `JOBHUNTER_PYTHON` env var (override for tests / CI).
2. `.venv/Scripts/python.exe` relative to `JOBHUNTER_ROOT` or `CWD`.
3. `py`, `python3`, `python` in PATH.

Set `JOBHUNTER_ROOT` to the project root if running the Tauri app from a different CWD.

## Build prerequisites (Windows)

Tauri v2 on Windows requires the MSVC toolchain.  Before running `cargo build`,
`cargo test`, or `npm run tauri build`, initialise the MSVC environment:

```bat
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
```

Or launch from a **Visual Studio 2022 Developer Command Prompt**.

> **Application Control note:** if `npm run tauri build` (release) is blocked by a Windows
> WDAC policy, use `npm run tauri build -- --debug` for debug builds.  The code is
> identical; only the optimisation level differs.  This is a machine-policy constraint,
> not a code issue.

## Conventions

- All Tauri commands are `async fn` (not `pub async fn`) — `pub` on a command function
  causes a Tauri 2.x macro name collision (`E0255`).
- Frontend events for streamed progress use the event name `pipeline-progress`.
- For C-031 the frontend is a static HTML placeholder; the Vue scaffold lands in C-032.

## Pointers

- Parent: [`../../AGENTS.md`](../../AGENTS.md)
- Python sidecar: [`../cli/AGENTS.md`](../cli/AGENTS.md)
- SDD §11.1 — Tauri–Python IPC architecture.
- DEV_PLAN §9.3 — progress event data contract.
- C-032 — Vue app scaffold (next chunk after this one).
