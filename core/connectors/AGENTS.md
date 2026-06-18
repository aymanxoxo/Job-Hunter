# core/connectors — job connectors (plugin contract + built-ins)

## Contents
- `base_connector.py` — `BaseConnector` ABC. **[C-005 · present]**
- `indeed_connector.py`, `linkedin_connector.py`, `mock_connector.py` — built-ins (later chunks).

## Contract (`BaseConnector`, SDD §4.1)
- Subclass and implement `async search(criteria) -> list[Job]` returning raw (unscored) jobs.
- Class attrs: `name` (display), `auth_methods: tuple[str, ...]` (ordered, default `("none",)` — resolved
  by the runner per ADR-002), `enabled`.
- Optional `async authenticate() -> bool` (default True; return False to skip the connector —
  fail-graceful).
- Connectors are independent — never import another connector/provider (ADR-001).
- Every connector must pass the reusable check in `tests/contracts/connector_contract.py` (SDD §12.2),
  which is parametrised over all discovered connectors once plugin discovery (C-009) lands.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md) · Spec: SDD §4.1 · Auth strategy: ADR-002.
