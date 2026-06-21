"""C-055 — build_runner passes model and batch_size to provider."""
from __future__ import annotations

from types import SimpleNamespace

from core.ai_providers import BaseAIProvider
from core.connectors import BaseConnector
from core.models.search_criteria import SearchCriteria
from core.runner import build_runner


class StubProvider(BaseAIProvider):
    name = "stub"
    auth_methods = ("none",)

    def __init__(self, *, model: str = "default", batch_size: int = 10, **_kw) -> None:
        self.model = model
        self.batch_size = batch_size

    async def generate_criteria(self, profile: str) -> SearchCriteria:
        return SearchCriteria(raw_profile=profile)

    async def score_jobs(self, jobs, criteria):
        return jobs


class StubConnector(BaseConnector):
    name = "stub-conn"
    auth_methods = ("none",)

    async def search(self, criteria):
        return []


def _config(*, model: str = "default-model", batch_size: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        ai=SimpleNamespace(provider="stub", model=model, batch_size=batch_size),
        connectors={},
        output=SimpleNamespace(directory="output/", format="both"),
    )


def _discover(directory, base):
    if base is BaseAIProvider and "ai_providers" in str(directory):
        return [StubProvider]
    if base is BaseConnector and "connectors" in str(directory):
        return [StubConnector]
    return []


def test_build_runner_passes_model_to_provider():
    runner = build_runner(_config(model="test-model"), discover=_discover)
    assert runner.provider.model == "test-model"


def test_build_runner_passes_batch_size_to_provider():
    runner = build_runner(_config(batch_size=5), discover=_discover)
    assert runner.provider.batch_size == 5
