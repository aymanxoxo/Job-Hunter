"""C-008 - ordered auth strategy resolver."""
from __future__ import annotations

import io
import json

from core.auth.auth_strategy import AuthResult, resolve_auth
from core.logging import Logger


def _logger():
    stream = io.StringIO()
    return Logger("test.auth", stream=stream, clock=lambda: "T"), stream


def test_none_auth_always_succeeds_without_credential():
    result = resolve_auth(("none",), plugin_name="mock")

    assert result == AuthResult(method="none", credential=None)


def test_first_success_wins_with_ordered_methods():
    calls: list[str] = []

    def oauth():
        calls.append("oauth")
        return {"access_token": "oauth-token"}

    result = resolve_auth(
        ("oauth", "api_key"),
        oauth_provider=oauth,
        api_key_env_var="GEMINI_API_KEY",
        env={"GEMINI_API_KEY": "api-token"},
        plugin_name="gemini",
    )

    assert result == AuthResult(method="oauth", credential={"access_token": "oauth-token"})
    assert calls == ["oauth"]


def test_falls_back_to_api_key_when_oauth_unavailable():
    result = resolve_auth(
        ("oauth", "api_key"),
        oauth_provider=lambda: None,
        api_key_env_var="GEMINI_API_KEY",
        env={"GEMINI_API_KEY": "api-token"},
        plugin_name="gemini",
    )

    assert result == AuthResult(method="api_key", credential="api-token")


def test_missing_api_key_falls_through_to_none():
    result = resolve_auth(
        ("api_key", "none"),
        api_key_env_var="OPENROUTER_API_KEY",
        env={},
        plugin_name="openrouter",
    )

    assert result == AuthResult(method="none", credential=None)


def test_session_provider_result_can_win():
    result = resolve_auth(
        ("session", "none"),
        session_provider=lambda: {"cookies": []},
        plugin_name="linkedin",
    )

    assert result == AuthResult(method="session", credential={"cookies": []})


def test_unmet_required_auth_returns_none_and_warns():
    logger, stream = _logger()

    result = resolve_auth(
        ("oauth", "api_key"),
        oauth_provider=lambda: None,
        api_key_env_var="GEMINI_API_KEY",
        env={},
        logger=logger,
        plugin_name="gemini",
    )

    assert result is None
    warning = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert warning["level"] == "WARNING"
    assert warning["plugin"] == "gemini"
    assert warning["auth_methods"] == ["oauth", "api_key"]
    assert warning["msg"] == "auth resolution failed"


def test_unknown_method_is_warned_and_skipped():
    logger, stream = _logger()

    result = resolve_auth(
        ("magic", "none"),
        logger=logger,
        plugin_name="custom",
    )

    assert result == AuthResult(method="none", credential=None)
    warning = json.loads(stream.getvalue().strip().splitlines()[0])
    assert warning["level"] == "WARNING"
    assert warning["auth_method"] == "magic"
    assert warning["msg"] == "unknown auth method skipped"
