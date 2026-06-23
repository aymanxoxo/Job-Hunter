"""Configuration models and loader (SDD §9).

Loads ``config.yaml``, overlays ``KEY__SUBKEY`` environment overrides (§9.2), and validates with
pydantic. Credentials are NEVER stored here — ``auth.*`` fields hold environment-variable *names*
(e.g. ``GEMINI_API_KEY``), enforced by a validator (ADR-002 / SDD §8). All sub-models use
``extra="forbid"`` so a stray/secret key fails loudly rather than being silently dropped (ADR-018).
``apply_env_overrides`` is pure; the only side effect is reading the YAML file.
"""
from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SECTIONS = ("ai", "profile", "connectors", "output", "auth")


class AIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "gemini"
    model: str = "gemini-3-flash"
    batch_size: int = Field(default=15, ge=1)
    min_score: int = Field(default=40, ge=0, le=100)


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = "text"


class ConnectorSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    max_results: int = Field(default=50, ge=1)
    delay_min: float = Field(default=2.0, ge=0)
    delay_max: float = Field(default=5.0, ge=0)
    fixture_path: str | None = None
    # DDG connector fields (ignored by other connectors)
    results_per_query: int = Field(default=10, ge=1)
    trust_threshold: int = Field(default=60, ge=0, le=100)
    trust_check_enabled: bool = True

    @model_validator(mode="after")
    def _delays_ordered(self) -> ConnectorSettings:
        if self.delay_min > self.delay_max:
            raise ValueError(
                f"delay_min ({self.delay_min}) must be <= delay_max ({self.delay_max})"
            )
        return self


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["csv", "json", "both"] = "both"
    directory: str = "output/"


class AuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gemini_api_key_env: str = "GEMINI_API_KEY"
    openrouter_api_key_env: str = "OPENROUTER_API_KEY"
    adzuna_app_id_env: str = "ADZUNA_APP_ID"
    adzuna_app_key_env: str = "ADZUNA_APP_KEY"

    @field_validator("*")
    @classmethod
    def _must_be_env_var_name(cls, value: str) -> str:
        if not _ENV_NAME.match(value):
            raise ValueError(
                f"auth.* must hold an ENV VAR NAME (e.g. GEMINI_API_KEY), not a secret: {value!r}"
            )
        return value


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ai: AIConfig = Field(default_factory=AIConfig)
    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    connectors: dict[str, ConnectorSettings] = Field(default_factory=dict)
    output: OutputConfig = Field(default_factory=OutputConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)


def apply_env_overrides(data: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    """Pure: overlay ``KEY__SUBKEY=value`` env vars onto a config dict (``__`` = nesting).

    Only env vars whose first segment is a known config section are applied; values stay as strings
    and are coerced by pydantic on validation. The input ``data`` is not mutated.
    """
    result = deepcopy(data)
    for key, value in env.items():
        if "__" not in key:
            continue
        parts = [segment.lower() for segment in key.split("__")]
        if parts[0] not in _SECTIONS:
            continue
        node: Any = result
        for segment in parts[:-1]:
            child = node.get(segment)
            if not isinstance(child, dict):
                child = {}
                node[segment] = child
            node = child
        node[parts[-1]] = value
    return result


def load_config(path: str | Path = "config.yaml", env: dict[str, str] | None = None) -> Config:
    """Read ``path``, apply env overrides, and return a validated ``Config``."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    merged = apply_env_overrides(raw, dict(os.environ) if env is None else env)
    return Config.model_validate(merged)
