"""C-003 — config models, YAML loader, env overrides, no-secrets rule (SDD §9).

Includes hardening from review (fix/config-models-hardening): strict unknown-key rejection,
output.format enum, and delay_min <= delay_max.
"""
import pytest
from pydantic import ValidationError

from core.config import (
    Config,
    ConnectorSettings,
    OutputConfig,
    apply_env_overrides,
    load_config,
)


def test_defaults():
    c = Config()
    assert c.ai.provider == "gemini" and c.ai.model == "gemini-3.5-flash"
    assert c.ai.batch_size == 15 and c.ai.min_score == 40
    assert c.profile.input == "text"
    assert c.output.format == "both"
    assert c.auth.gemini_api_key_env == "GEMINI_API_KEY"
    assert c.auth.adzuna_app_id_env == "ADZUNA_APP_ID"
    assert c.auth.adzuna_app_key_env == "ADZUNA_APP_KEY"


def test_load_config_reads_yaml(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "ai:\n  provider: ollama\n  batch_size: 7\n"
        "connectors:\n  mock:\n    enabled: true\n"
    )
    c = load_config(p, env={})
    assert c.ai.provider == "ollama" and c.ai.batch_size == 7
    assert c.connectors["mock"].enabled is True


def test_env_double_underscore_overrides(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("ai:\n  provider: gemini\nconnectors:\n  linkedin:\n    enabled: true\n")
    env = {
        "AI__PROVIDER": "ollama",
        "AI__BATCH_SIZE": "20",
        "CONNECTORS__LINKEDIN__ENABLED": "false",
    }
    c = load_config(p, env=env)
    assert c.ai.provider == "ollama"
    assert c.ai.batch_size == 20
    assert c.connectors["linkedin"].enabled is False


def test_env_override_preserves_sibling_config_on_invalid_path():
    """An env var with a path longer than the config structure must not replace a
    leaf with a dict."""
    data = {"ai": {"provider": "gemini", "model": "gemini-3.5-flash"}}
    env = {"AI__PROVIDER__EXTRA": "foo"}
    result = apply_env_overrides(data, env)
    assert result["ai"]["provider"] == "gemini"
    assert result["ai"]["model"] == "gemini-3.5-flash"


def test_apply_env_overrides_is_pure():
    data = {"ai": {"provider": "gemini"}}
    out = apply_env_overrides(data, {"AI__PROVIDER": "ollama"})
    assert out["ai"]["provider"] == "ollama"
    assert data["ai"]["provider"] == "gemini"
    assert apply_env_overrides({}, {"PATH": "/x", "FOO": "bar"}) == {}


def test_auth_must_be_env_var_names_not_secrets():
    with pytest.raises(ValidationError):
        Config(auth={"gemini_api_key_env": "sk-super-secret-123"})


def test_auth_accepts_valid_env_name():
    c = Config(auth={"gemini_api_key_env": "MY_GEMINI_KEY"})
    assert c.auth.gemini_api_key_env == "MY_GEMINI_KEY"


def test_unknown_keys_are_rejected():
    # a pasted secret under an unknown key must FAIL loudly — config.yaml stays safe to commit
    with pytest.raises(ValidationError):
        Config(auth={"gemini_api_key": "sk-secret"})   # unknown auth key (no _env)
    with pytest.raises(ValidationError):
        ConnectorSettings(api_key="sk-secret")          # unknown connector field
    with pytest.raises(ValidationError):
        Config(unknown_section={})                      # unknown top-level section


def test_unknown_key_in_yaml_rejected(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("connectors:\n  linkedin:\n    api_key: sk-LEAK\n")
    with pytest.raises(ValidationError):
        load_config(p, env={})


def test_output_format_is_constrained():
    for ok in ("csv", "json", "both"):
        assert OutputConfig(format=ok).format == ok
    with pytest.raises(ValidationError):
        OutputConfig(format="banana")


def test_connector_delay_min_le_max():
    ConnectorSettings(delay_min=1.0, delay_max=1.0)
    with pytest.raises(ValidationError):
        ConnectorSettings(delay_min=9.0, delay_max=1.0)
