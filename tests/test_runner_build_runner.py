"""C-053 — build_runner connector config wiring tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.ai_providers import BaseAIProvider
from core.connectors import BaseConnector
from core.models.search_criteria import SearchCriteria
from core.runner import build_runner


class StubProvider(BaseAIProvider):
    name = "stub"
    auth_methods = ("none",)

    def __init__(self, **_kw) -> None:
        pass

    async def generate_criteria(self, profile):
        return SearchCriteria(raw_profile=profile)

    async def score_jobs(self, jobs, criteria):
        return jobs


class AuthAwareProvider(BaseAIProvider):
    name = "gemini"
    auth_methods = ("api_key",)

    def __init__(
        self,
        *,
        api_key_env: str = "GEMINI_API_KEY",
        model: str = "default-model",
        batch_size: int = 15,
    ) -> None:
        self.api_key_env = api_key_env
        self.model = model
        self.batch_size = batch_size

    async def generate_criteria(self, profile):
        return SearchCriteria(raw_profile=profile)

    async def score_jobs(self, jobs, criteria):
        return jobs


class ConfigurableConnector(BaseConnector):
    """Stub connector that accepts the same config kwargs as real connectors."""

    name = "configurable"
    auth_methods = ("none",)

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_results: int = 50,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
    ) -> None:
        self.enabled = enabled
        self.max_results = max_results
        self.delay_min = delay_min
        self.delay_max = delay_max

    async def search(self, criteria):
        return []


class FixtureConnector(BaseConnector):
    """Stub connector that accepts fixture_path like MockConnector."""

    name = "fixture"
    auth_methods = ("none",)

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_results: int = 50,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        fixture_path: str | Path | None = None,
    ) -> None:
        self.enabled = enabled
        self.max_results = max_results
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.fixture_path = Path(fixture_path) if fixture_path else None

    async def search(self, criteria):
        return []


class AuthAwareAdzunaConnector(BaseConnector):
    name = "adzuna"
    auth_methods = ("api_key",)

    def __init__(
        self,
        *,
        app_id_env: str = "ADZUNA_APP_ID",
        app_key_env: str = "ADZUNA_APP_KEY",
        max_results: int = 50,
    ) -> None:
        self.app_id_env = app_id_env
        self.app_key_env = app_key_env
        self.max_results = max_results

    async def search(self, criteria):
        return []


def _config(**connector_settings):
    connectors = {}
    auth = connector_settings.pop("auth", None) or SimpleNamespace(
        gemini_api_key_env="GEMINI_API_KEY",
        openrouter_api_key_env="OPENROUTER_API_KEY",
        adzuna_app_id_env="ADZUNA_APP_ID",
        adzuna_app_key_env="ADZUNA_APP_KEY",
    )
    provider = connector_settings.pop("provider", "stub")
    for name, settings in connector_settings.items():
        if isinstance(settings, dict):
            connectors[name] = SimpleNamespace(**settings)
        else:
            connectors[name] = settings
    return SimpleNamespace(
        ai=SimpleNamespace(provider=provider, model="stub-model", batch_size=10),
        connectors=connectors,
        output=SimpleNamespace(directory="output/", format="both"),
        auth=auth,
    )


def _discover_factory(connector_classes, provider_classes=None):
    """Return a discover function that yields the given connector classes by name match."""

    def fake_discover(directory, base):
        if base is BaseAIProvider and "ai_providers" in str(directory):
            return list(provider_classes or [StubProvider])
        if base is BaseConnector and "connectors" in str(directory):
            return list(connector_classes)
        return []

    return fake_discover


def test_build_runner_passes_max_results_to_connector():
    discover = _discover_factory([ConfigurableConnector])
    config = _config(configurable={"max_results": 10})
    runner = build_runner(config, discover=discover)
    assert len(runner.connectors) == 1
    assert runner.connectors[0].max_results == 10


def test_build_runner_skips_disabled_connector():
    discover = _discover_factory([ConfigurableConnector])
    config = _config(configurable={"enabled": False})
    runner = build_runner(config, discover=discover)
    assert len(runner.connectors) == 0


def test_build_runner_passes_delay_to_connector():
    discover = _discover_factory([ConfigurableConnector])
    config = _config(configurable={"delay_min": 0.5, "delay_max": 1.0})
    runner = build_runner(config, discover=discover)
    assert len(runner.connectors) == 1
    assert runner.connectors[0].delay_min == 0.5
    assert runner.connectors[0].delay_max == 1.0


def test_build_runner_uses_defaults_when_no_config_section():
    discover = _discover_factory([ConfigurableConnector])
    config = _config()
    runner = build_runner(config, discover=discover)
    assert len(runner.connectors) == 1
    conn = runner.connectors[0]
    assert conn.enabled is True
    assert conn.max_results == 50
    assert conn.delay_min == 2.0
    assert conn.delay_max == 5.0


def test_build_runner_passes_fixture_path_to_mock():
    discover = _discover_factory([FixtureConnector])
    config = _config(fixture={"enabled": True, "fixture_path": "f.json"})
    runner = build_runner(config, discover=discover)
    assert len(runner.connectors) == 1
    assert runner.connectors[0].fixture_path == Path("f.json")


def test_build_runner_passes_auth_env_names_to_provider_and_connector():
    discover = _discover_factory([AuthAwareAdzunaConnector], provider_classes=[AuthAwareProvider])
    config = _config(
        provider="gemini",
        auth=SimpleNamespace(
            gemini_api_key_env="MY_GEMINI_KEY",
            openrouter_api_key_env="MY_OPENROUTER_KEY",
            adzuna_app_id_env="MY_ADZUNA_ID",
            adzuna_app_key_env="MY_ADZUNA_KEY",
        ),
        adzuna={"max_results": 3},
    )

    runner = build_runner(config, discover=discover)

    assert runner.provider.api_key_env == "MY_GEMINI_KEY"
    assert runner.provider.model == "stub-model"
    assert runner.provider.batch_size == 10
    assert len(runner.connectors) == 1
    assert runner.connectors[0].app_id_env == "MY_ADZUNA_ID"
    assert runner.connectors[0].app_key_env == "MY_ADZUNA_KEY"
    assert runner.connectors[0].max_results == 3
