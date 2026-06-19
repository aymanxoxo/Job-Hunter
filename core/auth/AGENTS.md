# core/auth - authentication strategy and stores

## Contents
- `auth_strategy.py` - ordered auth resolver for plugin `auth_methods`.
- `__init__.py` - exports the resolver contract.

## Contracts
- `resolve_auth()` tries methods in declared order and returns the first successful `AuthResult`.
- `none` always succeeds without a credential.
- `api_key` reads an injected env mapping via the configured env-var name; credentials never come from committed config values.
- `oauth` and `session` are injected callables in C-008; real Google OAuth and session-store implementations land in later chunks.
- If required auth cannot be resolved, return `None` and warn through structured logging so the runner can skip the plugin gracefully.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Spec: `../../Documents/JobHunter_SDD_v1.1.md` §8.1
- Decisions: `../../Documents/DECISIONS.md` ADR-002
