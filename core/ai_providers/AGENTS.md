# core/ai_providers - AI provider contracts and built-ins

## Contents
- `base_provider.py` - `BaseAIProvider` ABC. **[C-006 present]**
- `ollama_provider.py` - local Ollama `/api/generate` provider. **[C-015 present]**
- `gemini_provider.py`, `openrouter_provider.py` - built-ins planned for later chunks.

## Contract (`BaseAIProvider`, SDD section 4.2)
- Subclass and implement `async generate_criteria(profile: str) -> SearchCriteria`.
- Subclass and implement `async score_jobs(jobs, criteria) -> list[Job]`; return new scored `Job`
  instances rather than mutating input jobs.
- Class attrs: `name` (display), `auth_methods: tuple[str, ...]` (ordered, default `("api_key",)`,
  resolved by the runner per ADR-002), `supports_local`.
- Optional `async initialize() -> None` startup hook (default no-op).
- Providers are independent: never import another provider/connector (ADR-001).
- Every provider must pass the reusable checks in `tests/contracts/provider_contract.py`.
- `OllamaProvider` is local-only: default model `llama3`, endpoint
  `http://localhost:11434/api/generate`, `auth_methods = ("none",)`, and fake HTTP in tests.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Spec: `../../Documents/JobHunter_SDD_v1.1.md` sections 4.2 and 7.2
- Auth strategy: ADR-002
