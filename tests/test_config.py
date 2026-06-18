"""C-003 — config models, YAML loader, env overrides, no-secrets rule (SDD §9)."""
import pytest
from pydantic import ValidationError

from core.config import Config, apply_env_overrides, load_config


def test_defaults():
    c = Config()
    assert c.ai.provider == "gemini" and c.ai.model == "gemini-3-flash"
    assert c.ai.batch_size == 15 and c.ai.min_score == 40
    assert c.profile.input == "text"
    assert c.output.format == "both"
    assert c.auth.gemini_api_key_env == "GEMINI_API_KEY"


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
