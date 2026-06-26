# core/connectors - job connector contracts and built-ins

## Contents
- `base_connector.py` - `BaseConnector` ABC. **[C-005 present]**
- `mock_connector.py` - fixture-backed offline connector. **[C-018 present]**
- `adzuna_connector.py` - sanctioned Adzuna jobs API connector. **[C-051 present]**
- `indeed_connector.py`, `linkedin_connector.py` - blocked direct-scraping connectors; superseded by Adzuna.

## Contract (`BaseConnector`, SDD section 4.1)
- Subclass and implement `async search(criteria) -> list[Job]` returning raw, unscored jobs.
- Class attrs: `name` (display), `auth_methods: tuple[str, ...]` (ordered, default `("none",)`,
  resolved by the runner per ADR-002), `enabled`.
- Optional `async authenticate() -> bool` defaults to `True`; return `False` to skip a connector
  fail-gracefully.
- Connectors are independent: never import another connector/provider (ADR-001).
- Every connector must pass the reusable check in `tests/contracts/connector_contract.py`.
- `MockConnector` reads `fixtures/jobs.json` by default, accepts a `fixture_path` override, enforces
  `source = "mock"`, and filters with a simple case-insensitive keyword match against title and
  description.
- `AdzunaConnector` uses the official Adzuna API, reads `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` by default,
  maps Adzuna results to `Job`, and keeps credentials out of source/config values.
- `DDGConnector` (`duckduckgo_connector.py`, C-020): open-web discovery + AI purification + optional
  trust scoring. Per-company trust scoring and per-URL page fetches run concurrently under a single
  `asyncio.Semaphore(max_concurrency)` (default 5) so a wide result set cannot fan out unbounded
  (C-073). `_is_safe_url` vets the literal URL host; `_real_http_fetch` additionally resolves the host
  and **pins the connection to a re-validated public IP** (`_resolve_public_ip`), refusing any
  private/loopback resolution and not following redirects — closing the DNS-rebind/SSRF window (C-073).

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Spec: `../../Documents/JobHunter_SDD_v1.1.md` sections 4.1 and 6.3
- Auth strategy: ADR-002
