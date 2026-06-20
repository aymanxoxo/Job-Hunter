"""Auth status and logout CLI commands (C-027)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import click
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from core.auth import SessionStore
from core.auth.session_store import DEFAULT_SESSION_DIR
from core.config import Config, load_config

CONFIG_PATH = Path("config.yaml")


@click.group(name="auth")
@click.option(
    "--session-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    help="Encrypted session directory. Defaults to ~/.jobhunter/sessions.",
)
@click.pass_context
def auth_group(ctx: click.Context, session_dir: Path | None) -> None:
    """Inspect and clear configured auth state."""
    ctx.ensure_object(dict)
    ctx.obj["session_dir"] = session_dir


@auth_group.command(name="status")
@click.pass_context
def auth_status(ctx: click.Context) -> None:
    """Show API-key and session auth status without printing secrets."""
    config = _load_config()
    table = Table(title="Auth Status")
    table.add_column("Service")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Source")
    for row in _status_rows(config, session_store=_session_store(ctx)):
        table.add_row(row.service, row.kind, row.status, row.source)
    _console().print(table)


@auth_group.command(name="logout")
@click.argument("service")
@click.pass_context
def auth_logout(ctx: click.Context, service: str) -> None:
    """Delete stored session auth for a service."""
    config = _load_config()
    normalized = service.lower()
    if normalized in _API_KEY_SERVICES:
        env_name = _api_key_env_names(config)[normalized]
        raise click.ClickException(
            f"{normalized} uses env-var auth; unset {env_name} in your shell to log out."
        )
    if normalized not in _SESSION_SERVICES:
        allowed = ", ".join(sorted((*_API_KEY_SERVICES, *_SESSION_SERVICES)))
        raise click.ClickException(f"Unknown auth service {service!r}; expected one of: {allowed}.")
    _session_store(ctx).delete(normalized)
    click.echo(f"Logged out: {normalized}")


@auth_group.command(name="google")
def auth_google() -> None:
    """Deferred OAuth device-flow command."""
    raise click.ClickException("Google OAuth device flow is deferred to C-016.")


@auth_group.command(name="linkedin")
def auth_linkedin() -> None:
    """Deferred browser-session login command."""
    raise click.ClickException(
        "LinkedIn session login is deferred with the blocked C-021 connector."
    )


def register_cli(main: click.Group) -> None:
    """Attach C-027 auth commands to the root CLI."""
    main.add_command(auth_group)


@dataclass(frozen=True)
class AuthStatusRow:
    service: str
    kind: str
    status: str
    source: str


_API_KEY_SERVICES = ("gemini", "openrouter", "adzuna")
_SESSION_SERVICES = ("linkedin",)


def _status_rows(config: Config, *, session_store: SessionStore) -> list[AuthStatusRow]:
    rows: list[AuthStatusRow] = []
    env_names = _api_key_env_names(config)
    for service in _API_KEY_SERVICES:
        names = env_names[service]
        required = (names,) if isinstance(names, str) else names
        present = [name for name in required if os.environ.get(name)]
        rows.append(
            AuthStatusRow(
                service=service,
                kind="api_key",
                status="configured" if len(present) == len(required) else "missing",
                source=", ".join(required),
            )
        )
    for service in _SESSION_SERVICES:
        rows.append(
            AuthStatusRow(
                service=service,
                kind="session",
                status="stored" if session_store.exists(service) else "missing",
                source=str(session_store.root_dir),
            )
        )
    return rows


def _api_key_env_names(config: Config) -> dict[str, str | tuple[str, str]]:
    return {
        "gemini": config.auth.gemini_api_key_env,
        "openrouter": config.auth.openrouter_api_key_env,
        "adzuna": (config.auth.adzuna_app_id_env, config.auth.adzuna_app_key_env),
    }


def _session_store(ctx: click.Context) -> SessionStore:
    obj = ctx.obj or {}
    root_dir = obj.get("session_dir") or DEFAULT_SESSION_DIR
    return SessionStore(
        root_dir=root_dir,
        keyring_backend=obj.get("keyring_backend"),
        machine_id_provider=obj.get("machine_id_provider"),
    )


def _load_config(path: Path = CONFIG_PATH) -> Config:
    try:
        return load_config(path)
    except FileNotFoundError as exc:
        raise click.ClickException(f"Config file not found: {path}") from exc
    except ValidationError as exc:
        raise click.ClickException(f"Config is invalid: {exc}") from exc


def _console() -> Console:
    return Console(color_system=None, force_terminal=False)
