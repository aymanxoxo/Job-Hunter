"""Ordered auth strategy resolver (SDD §8.1)."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

AuthProvider = Callable[[], Any | None]


@dataclass(frozen=True)
class AuthResult:
    """The method that authenticated a plugin and the credential it produced, if any."""

    method: str
    credential: Any = None


def resolve_auth(
    auth_methods: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    api_key_env_var: str | None = None,
    oauth_provider: AuthProvider | None = None,
    session_provider: AuthProvider | None = None,
    logger: Any | None = None,
    plugin_name: str = "plugin",
) -> AuthResult | None:
    """Try ``auth_methods`` in order; return the first successful method or ``None``."""
    log = logger or get_logger("core.auth.strategy")
    methods = tuple(auth_methods)
    values = {} if env is None else env

    for method in methods:
        if method == "none":
            return AuthResult(method="none")
        if method == "oauth":
            if result := _try_provider("oauth", oauth_provider):
                return result
            continue
        if method == "api_key":
            if result := _try_api_key(values, api_key_env_var):
                return result
            continue
        if method == "session":
            if result := _try_provider("session", session_provider):
                return result
            continue
        log.warning(
            "unknown auth method skipped",
            plugin=plugin_name,
            auth_method=method,
        )

    log.warning(
        "auth resolution failed",
        plugin=plugin_name,
        auth_methods=list(methods),
    )
    return None


def _try_provider(method: str, provider: AuthProvider | None) -> AuthResult | None:
    if provider is None:
        return None
    credential = provider()
    if credential is None:
        return None
    return AuthResult(method=method, credential=credential)


def _try_api_key(env: Mapping[str, str], api_key_env_var: str | None) -> AuthResult | None:
    if not api_key_env_var:
        return None
    value = env.get(api_key_env_var)
    if not value:
        return None
    return AuthResult(method="api_key", credential=value)
