# tools - deterministic workflow automation

## Contents
- `jh.py` - AI-facing workflow harness for bootstrap, status, next, start, doctor, gate, PR handoff,
  and post-merge cleanup.
- `jh_config.json` - deterministic chunk metadata used by the harness.
- `README.md` - command guide for any AI agent taking over the workflow.

## Contracts
- Keep reusable workflow logic as pure functions; CLI commands are the thin imperative shell.
- Write generated logs/evidence only under git-ignored `output/agent/`.
- Never print secrets, tokens, or credential values. Capability checks may detect access but must not
  expose credentials.

## Conventions
- Prefer stdlib-only harness code so a fresh agent can run it before project dependencies are present.
- Mutating git/GitHub operations must be explicit commands; pure helpers and dry-run planning stay
  testable without network or credentials.
- Direct PR creation should use every safe credential source before falling back: authenticated `gh`,
  OAuth device flow via `auth-login`, `JH_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN`, then Git Credential
  Manager via `git credential fill`.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Workflow: [../HANDOFF.md](../HANDOFF.md)
- Decision: [../Documents/DECISIONS.md](../Documents/DECISIONS.md)
