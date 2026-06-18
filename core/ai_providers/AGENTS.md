# core/ai_providers — AI provider contracts + built-ins

## Contents
- `base_provider.py` — `BaseAIProvider` ABC. **[C-006 · present]**
- `gemini_provider.py`, `ollama_provider.py`, `openrouter_provider.py` — built-ins (later chunks).

## Contract (`BaseAIProvider`, SDD §4.2)
- Subclass and implement `async generate_criteria(profile: str) -> SearchCriteria`.
- Subclass and implement `async score_jobs(jobs, criteria) -> list[Job]`; return new scored `Job`
  instances rather than mutating input jobs.
- Class attrs: `name` (display), `auth_methods: tuple[str, ...]` (ordered, default `("api_key",)` —
  resolved by the runner per ADR-002), `supports_local`.
- Optional `async initialize() -> None` startup hook (default no-op).
- Providers are independent — never import another provider/connector (ADR-001).
- Every provider must pass the reusable checks in `tests/contracts/provider_contract.py`, which are
  parametrised over all discovered providers once plugin discovery (C-009) lands.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md) · Spec: SDD §4.2 · Auth strategy: ADR-002.
