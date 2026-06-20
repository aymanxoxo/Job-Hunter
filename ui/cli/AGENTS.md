# ui/cli - Click/Rich command interface

## Contents
- `cli.py` - `jobhunter run` (real `core.runner` pipeline + Rich render, C-026) and the config_cmd groups.
- `config_cmd.py` - C-028 `config show`, plugin list, and result re-export commands.
- `__init__.py` - package marker.

## Contracts
- CLI commands may write human output to stdout. Core modules must not.
- Keep command handlers thin: parse options, call core functions, render results.
- `run` drives the real `core.runner` pipeline (C-026); progress events go to stderr so stdout stays the table.
- `export --format` re-exports the newest `results_*.json` file from the configured output directory.

## Pointers
- Parent: [../../AGENTS.md](../../AGENTS.md)
- Dev plan: `Documents/JobHunter_DEV_PLAN_v1.0.md` C-026, C-028, and C-050.
