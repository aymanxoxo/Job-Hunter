# tools - deterministic workflow automation

## Contents
- `jh.py` - AI-facing workflow harness for bootstrap, status, next, start, doctor, gate, PR handoff,
  and post-merge cleanup.
- `chunks.json` - the chunk registry: single source of truth for per-chunk metadata (stage/deps/risk/tests) + smoke imports (ADR-024); `doctor` checks it against the ledger and dev-plan §10.
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
- Long-running ops are async-by-default and idempotent (ADR-023): `merge-pr` checks once (`--wait` is opt-in, hard-capped at 300s), an already-merged PR / already-deleted branch return success immediately, and `pr-status <#>` is a non-blocking readiness poll.
- Auto-merge must go through `merge-pr`; it only merges explicitly allowed PR classes after GitHub reports
  the exact head SHA is mergeable and all checks succeeded.
- Before creating a branch for a chunk/code change, ask the user if this PR should opt into CI native
  auto-merge. Record the answer in the PR body checkbox or `auto-merge` label.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Workflow: [../HANDOFF.md](../HANDOFF.md)
- Decision: [../Documents/DECISIONS.md](../Documents/DECISIONS.md)
