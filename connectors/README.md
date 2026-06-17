# connectors/ — user drop-zone

Drop a `*.py` file here defining **one** class that inherits
`core.connectors.base_connector.BaseConnector`. It is auto-discovered at startup via `importlib` — no
registration. Built-in connectors live in `core/connectors/`. See SDD §2.1 / §14.1.
