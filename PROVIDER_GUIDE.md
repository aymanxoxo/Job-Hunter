# AI Provider Authoring Guide

An AI provider converts profile text into `SearchCriteria` and scores raw jobs. Providers can be
built in under `core/ai_providers/` or dropped into the user `ai_providers/` directory.

## Contract

Every provider must inherit `BaseAIProvider`:

```python
from core.ai_engine import AIEngine
from core.ai_providers.base_provider import BaseAIProvider
from core.models.job import Job
from core.models.search_criteria import SearchCriteria


class ExampleProvider(BaseAIProvider):
    name = "example-ai"
    auth_methods = ("api_key",)
    supports_local = False

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        return await self._engine().generate_criteria(profile)

    async def score_jobs(self, jobs: list[Job], criteria: SearchCriteria) -> list[Job]:
        return await self._engine().score_jobs(jobs, criteria)

    async def _call(self, prompt: str) -> str:
        # Send prompt to the model and return the provider's text response.
        ...

    def _engine(self) -> AIEngine:
        return AIEngine(self._call, batch_size=15)
```

Required class attributes:

- `name`: selected by `config.yaml` under `ai.provider`.
- `auth_methods`: ordered methods such as `("none",)`, `("api_key",)`, or `("oauth", "api_key")`.
- `supports_local`: `True` only for local providers such as Ollama.

Required methods:

- `generate_criteria(profile: str) -> SearchCriteria`
- `score_jobs(jobs: list[Job], criteria: SearchCriteria) -> list[Job]`

Optional method:

- `initialize()` for health checks or token refresh.

## Use AIEngine

Prefer delegating prompt construction, batching, response parsing, and immutable `Job` scoring to
`AIEngine`. That keeps provider code as a thin HTTP shell:

- Build/send the provider request.
- Return the model text.
- Let `AIEngine` parse criteria/scored jobs.

Built-in `ollama`, `openrouter`, and `gemini` are good examples.

## Discovery

Discovery scans direct `*.py` files only:

- Built-ins: `core/ai_providers/`
- User drop-zone: `ai_providers/`

Files starting with `_` or `base_` are skipped. No registration file is needed.

## Config And Auth

Select the provider in `config.yaml`:

```yaml
ai:
  provider: example-ai
  model: example-model
  batch_size: 15
auth:
  example_api_key_env: EXAMPLE_API_KEY
```

If you add a new built-in provider with new auth config, update `core/config.py`, `config.yaml`, and
the relevant docs in the same change.

Never commit API keys. Read env vars at call time, and never log credential values.

## Tests

Add a focused test file such as `tests/test_example_provider.py`.

Use a fake client or `httpx.MockTransport`; never require network in tests. Include the reusable
contract checks:

```python
from tests.contracts.provider_contract import (
    assert_provider_generates_valid_criteria,
    assert_provider_scores_valid_jobs,
)
```

Run:

```bash
python -m pytest tests/test_example_provider.py -q --asyncio-mode=auto
python tools/jh.py gate C-XXX
```

## Checklist

- The class inherits `BaseAIProvider`.
- `generate_criteria` returns `SearchCriteria`.
- `score_jobs` returns new scored `Job` objects without mutating inputs.
- Provider calls are deterministic in tests.
- Auth is env-backed and secrets are never logged.
- Focused tests cover success, auth failure, malformed response, and HTTP failure.
- The tests use `tests/contracts/provider_contract.py`.
