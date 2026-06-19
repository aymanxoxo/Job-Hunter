# core/auth - authentication strategy and stores

## Contents
- `auth_strategy.py` - ordered auth resolver for plugin `auth_methods`. **[C-008 present]**
- `session_store.py` - encrypted Playwright storage-state session store. **[C-019 present]**
- `__init__.py` - exports the auth resolver and session-store contract.

## Contracts
- `resolve_auth()` tries methods in declared order and returns the first successful `AuthResult`.
- `none` always succeeds without a credential.
- `api_key` reads an injected env mapping via the configured env-var name; credentials never come from
  committed config values.
- `oauth` remains injectable in C-008; real Google OAuth lands in C-016.
- `SessionStore.save(name, state_dict)` encrypts and writes Playwright storage state to
  `~/.jobhunter/sessions/{name}.enc` by default.
- `SessionStore.load(name)` decrypts and returns a storage-state dict; invalid encrypted payloads raise
  `SessionStoreError`.
- Session keys are derived with PBKDF2HMAC/SHA-256 from a machine identifier and stored through the OS
  keyring API; tests inject a fake keyring.
- Session names are restricted to safe filename characters so callers cannot escape the session folder.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Spec: `../../Documents/JobHunter_SDD_v1.1.md` sections 8.1 and 8.3
- Decisions: `../../Documents/DECISIONS.md` ADR-002
