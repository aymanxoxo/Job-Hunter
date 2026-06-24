# core/ai_providers - AI provider contracts and built-ins

## Contents
- `base_provider.py` - `BaseAIProvider` ABC. **[C-006 present]**
- `ollama_provider.py` - local Ollama `/api/generate` provider. **[C-015 present]**
- `openrouter_provider.py` - OpenRouter OpenAI-compatible provider. **[C-030 present]**
- `gemini_provider.py` - Gemini `generateContent` provider (oauth/api_key). **[C-017 present]**

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
- `OpenRouterProvider` calls the OpenAI-compatible `chat/completions` endpoint with a `Bearer`
  API key read from `$OPENROUTER_API_KEY` at call time (never stored/logged); default model
  `qwen/qwen3-coder:free` with fallback `deepseek/deepseek-r1:free` on error; fake HTTP in tests.
- `GeminiProvider` calls Google's `generateContent`; auth resolved via `auth_strategy` (C-008) —
  OAuth bearer when a token provider is wired (C-016), else `x-goog-api-key` from `$GEMINI_API_KEY`
  (read at call time, never logged); default model `gemini-3.5-flash`; fake HTTP in tests.
- Provider HTTP retries go through `_retry.http_call_with_retry()`, which retries 429/500/502/503/504
  and transient network failures, honors `Retry-After` when supplied, and rejects `max_attempts < 1`.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Spec: `../../Documents/JobHunter_SDD_v1.1.md` sections 4.2, 7.1, 7.2, and 7.3
- Auth strategy: ADR-002
