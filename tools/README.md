# JobHunter workflow harness

`tools/jh.py` is the deterministic helper for AI agents working on this repo. Use it for mechanical
workflow steps so model tokens stay focused on design, code, and review judgment.

## First commands

```bash
python tools/jh.py guide
python tools/jh.py bootstrap
python tools/jh.py status
python tools/jh.py next
```

If the shell does not expose `python`, use the available interpreter for the current runtime. On Windows,
`py -3 tools/jh.py ...` is usually equivalent.

## Normal chunk flow

```bash
python tools/jh.py start C-XXX --branch chunk/C-XXX-slug
python tools/jh.py gate C-XXX
python tools/jh.py pr-ready C-XXX
python tools/jh.py auth-status
python tools/jh.py create-pr C-XXX
python tools/jh.py merge-pr <PR_NUMBER>          # async: one readiness check, no long block (ADR-023)
python tools/jh.py pr-status <PR_NUMBER>         # non-blocking poll between turns
python tools/jh.py after-merge C-XXX --branch chunk/C-XXX-slug
```

Generated logs and PR evidence are written under `output/agent/`, which is git-ignored.

Risk-flagged chunks are blocked by `start` until design sign-off is complete. After sign-off, use:

```bash
python tools/jh.py start C-XXX --branch chunk/C-XXX-slug --allow-risk
```

## GitHub credentials

`create-pr` tries these routes in order:

1. `gh pr create`, if the GitHub CLI is installed and authenticated.
2. GitHub OAuth device flow captured by `python tools/jh.py auth-login`.
3. GitHub REST API using `JH_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN`.
4. GitHub REST API using the token returned by `git credential fill` for `https://github.com`.
5. Compare URL fallback if direct PR creation is unavailable.
6. Patch/title/body fallback if branch push is unavailable.

Preferred token: fine-grained GitHub PAT for this repository with:

- Contents: read/write, for branch push when the token is used by git.
- Pull requests: read/write, for direct PR creation.

For OAuth device flow:

```bash
python tools/jh.py auth-login --client-id <github-oauth-app-client-id>
```

The OAuth app must have device flow enabled. Use scope `repo` for private repositories unless the repo
owner has chosen a narrower OAuth app policy. The captured token is stored with Git Credential Manager via
`git credential approve`; it is never written to the repo.

Never write a token into repo files. Put it in the process environment, the runtime secret store, `gh`
auth, or Git Credential Manager. The harness reports credential source only; it never prints token values.

## Machine-readable output

Use these when another tool or model needs structured state:

```bash
python tools/jh.py status --json
python tools/jh.py auth-status --json
```

## CI-gated auto-merge

Use auto-merge only when the user has allowed it for the PR class. The harness refuses to merge unless
GitHub reports the PR is open, non-draft, mergeable, and every check run/status for the head commit has
completed successfully.

Before starting a chunk or code change, ask the user whether the resulting PR should auto-merge after
green CI. Encode the answer with either:

- the `auto-merge` label, or
- the checked PR body line `- [x] Auto-merge after CI`.

```bash
python tools/jh.py merge-pr <PR_NUMBER> --delete-branch   # add --wait <=300 to block (opt-in, ADR-023)
```

If checks are pending, failed, missing, or mergeability is unknown, the command exits nonzero and prints
the exact blocker. `--dry-run` verifies readiness without merging.

The GitHub Actions workflow runs the same policy automatically after the validation job. PRs that do not
opt in are skipped with a successful no-op.
