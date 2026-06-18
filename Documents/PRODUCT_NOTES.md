# JobHunter — Product Notes (business documentation)

> The **business / product** companion to the technical docs (which live in module `AGENTS.md` files).
> One short entry per feature/chunk that encodes user value or a business rule, tagged with its chunk ID.
> Added in the same PR as the chunk (ADR-017), only when the chunk warrants it. For substantial topics,
> link out to `docs/business/<topic>.md`.

## Entries (newest first)

### C-003 — Configuration & the no-secrets guarantee

JobHunter is configured through a single `config.yaml`: users choose the AI provider and model, the
scoring batch size, the score threshold that filters results, per-connector enable/limits/delays, and
the output format. Any setting can be overridden by an environment variable (e.g. `AI__PROVIDER=ollama`).

**Trust / security rule:** `config.yaml` **never** holds secrets. The `auth.*` entries are environment-
variable *names* (e.g. `GEMINI_API_KEY`), and a validator rejects anything that looks like a pasted key —
so the config file is always safe to commit or share. Real credentials live only in env vars / the OS
secret store (ADR-002, SDD §8).
