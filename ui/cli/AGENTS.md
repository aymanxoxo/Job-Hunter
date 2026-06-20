# ui/cli - Click/Rich command interface

## Contents
- `cli.py` - C-039 walking-skeleton `jobhunter run` command.
- `config_cmd.py` - C-028 `config show`, plugin list, and result re-export commands.
- `__init__.py` - package marker.

## Contracts
- CLI commands may write human output to stdout. Core modules must not.
- Keep command handlers thin: parse options, call core functions, render results.
- The C-039 command is temporary skeleton wiring; the final CLI runner lands in C-026.
- `export --format` re-exports the newest `results_*.json` file from the configured output directory.

## Pointers
- Parent: [../../AGENTS.md](../../AGENTS.md)
- Core skeleton: [../../core/walking_skeleton.py](../../core/walking_skeleton.py)
- Dev plan: `Documents/JobHunter_DEV_PLAN_v1.0.md` C-026, C-028, and C-039.
