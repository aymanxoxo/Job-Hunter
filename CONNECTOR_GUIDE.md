# Connector Authoring Guide

A connector fetches raw, unscored jobs from one source and returns `Job` objects. Connectors can be
built in under `core/connectors/` or dropped into the user `connectors/` directory.

## Contract

Every connector must inherit `BaseConnector`:

```python
from core.connectors.base_connector import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria


class ExampleConnector(BaseConnector):
    name = "example"
    auth_methods = ("none",)

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        return [
            Job(
                id="example-1",
                title="Python Developer",
                company="Acme",
                url="https://example.test/jobs/1",
                source=self.name,
            )
        ]
```

Required class attributes:

- `name`: the config/discovery name. It must match `Job.source`.
- `auth_methods`: ordered auth methods such as `("none",)`, `("api_key",)`, `("session",)`, or
  `("oauth", "api_key")`.
- `enabled`: optional class default; runtime config can still disable a connector.

Required method:

- `async def search(criteria: SearchCriteria) -> list[Job]`

Optional method:

- `async def authenticate() -> bool`; return `False` to skip the connector gracefully.

## Discovery

Discovery scans direct `*.py` files only:

- Built-ins: `core/connectors/`
- User drop-zone: `connectors/`

Files starting with `_` or `base_` are skipped. No registration file is needed.

## Config

Enable user connectors by name in `config.yaml`:

```yaml
connectors:
  example:
    enabled: true
    max_results: 25
    delay_min: 1.0
    delay_max: 3.0
```

Do not put credentials in `config.yaml`. Store env-var names under `auth.*`, and read actual values
from the environment at runtime.

## Mapping SearchCriteria

Use the fields that make sense for the source:

- `criteria.titles`
- `criteria.keywords`
- `criteria.exclude_keywords`
- `criteria.locations`
- `criteria.max_results`
- `criteria.date_posted_days`

Return raw, unscored `Job` objects. Leave `score`, `match_reason`, and `red_flags` for the AI scoring
pipeline.

## Error Handling

Raise clear connector-specific errors for bad responses or malformed fixtures. The runner catches
connector exceptions, logs them to stderr, and continues with other connectors.

Avoid logging secrets, cookies, authorization headers, raw tokens, or full credential-bearing URLs.

## Tests

Add a focused test file such as `tests/test_example_connector.py`.

Use `httpx.MockTransport` or fixture files; never require network in tests. Include the reusable
contract check:

```python
from tests.contracts.connector_contract import assert_connector_returns_valid_jobs


async def test_example_connector_contract():
    connector = ExampleConnector(...)
    await assert_connector_returns_valid_jobs(connector, SearchCriteria(keywords=("python",)))
```

Run:

```bash
python -m pytest tests/test_example_connector.py -q --asyncio-mode=auto
python tools/jh.py gate C-XXX
```

## Checklist

- The class inherits `BaseConnector`.
- `search` returns `list[Job]`.
- Every returned `Job.source` equals `connector.name`.
- Credentials are env-backed and never committed.
- HTTP/file parsing is covered by deterministic tests.
- The focused tests use `tests/contracts/connector_contract.py`.
