# JobHunter

JobHunter is a local, plugin-based AI job-search aggregator. It turns a plain-text profile into
structured search criteria, runs job-source connectors, scores the results through an AI provider,
and exports ranked jobs to CSV and JSON.

The project is intentionally plugin-first: built-ins live under `core/`, while local drop-ins can be
placed in `connectors/`, `ai_providers/`, or `profile_inputs/` without editing a registry.

## Current Capabilities

- CLI pipeline: `jobhunter run --profile "Senior Python developer seeking remote work"`
- Built-in connectors: `mock` fixture connector and `adzuna` API connector.
- Built-in providers: `ollama`, `openrouter`, and `gemini`.
- Profile input: text passthrough, with PDF/Word/image parsers designed as future drop-ins.
- Auth/status commands for env-backed API keys and encrypted session-store state.
- Timestamped result export to `output/results_<timestamp>.csv` and/or `.json`.

## Setup

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev]
```

Set provider and connector credentials as environment variables. `config.yaml` stores env-var names,
not credential values.

```bash
set GEMINI_API_KEY=...
set OPENROUTER_API_KEY=...
set ADZUNA_APP_ID=...
set ADZUNA_APP_KEY=...
```

Useful commands:

```bash
jobhunter config show
jobhunter providers list
jobhunter connectors list
jobhunter auth status
jobhunter run --profile "Senior Python developer seeking remote work"
jobhunter export --format csv
```

## Authoring Plugins

Use these guides when adding local drop-ins or new built-ins:

- [CONNECTOR_GUIDE.md](CONNECTOR_GUIDE.md) - add a job-source connector.
- [PROVIDER_GUIDE.md](PROVIDER_GUIDE.md) - add an AI provider.
- [PROFILE_INPUT_GUIDE.md](PROFILE_INPUT_GUIDE.md) - add a profile input parser.

## Development Workflow

The chunk workflow is driven by `tools/jh.py`.

```bash
.venv\Scripts\python.exe tools\jh.py status
.venv\Scripts\python.exe tools\jh.py next
.venv\Scripts\python.exe tools\jh.py context C-XXX
.venv\Scripts\python.exe tools\jh.py gate C-XXX
```

Before submitting a chunk, run the gate. It runs the focused chunk tests, the full pytest suite,
Ruff, deterministic doctor checks, and import smoke.

## Documentation Map

- `AGENTS.md` is the orientation layer for agents and maintainers.
- `HANDOFF.md` is the quick takeover note.
- `Documents/JobHunter_SDD_v1.1.md` is the software design document.
- `Documents/JobHunter_DEV_PLAN_v1.0.md` is the chunk plan.
- `PROGRESS.md` is the live tracker.
