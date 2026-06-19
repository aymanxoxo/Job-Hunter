# core/connectors - job connector contracts and built-ins

## Contents
- `base_connector.py` - `BaseConnector` ABC. **[C-005 present]**
- `mock_connector.py` - fixture-backed offline connector. **[C-018 present]**
- `indeed_connector.py`, `linkedin_connector.py` - built-ins planned for later chunks.

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

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Spec: `../../Documents/JobHunter_SDD_v1.1.md` sections 4.1 and 6.3
- Auth strategy: ADR-002
