"""C-005 — BaseConnector ABC contract (SDD §4.1)."""
import types

import pytest

from core.connectors import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from tests.contracts.connector_contract import assert_connector_returns_valid_jobs


class _DummyConnector(BaseConnector):
    name = "dummy"

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        return [Job(id="1", title="Dev", company="Acme", url="https://x", source=self.name)]


def test_base_connector_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseConnector()


def test_subclass_without_search_is_abstract():
    class NoSearch(BaseConnector):
        pass

    with pytest.raises(TypeError):
        NoSearch()


def test_defaults():
    c = _DummyConnector()
    assert c.name == "dummy"
    assert c.auth_methods == ("none",)
    assert c.enabled is True


async def test_authenticate_defaults_to_true():
    assert await _DummyConnector().authenticate() is True


async def test_search_meets_connector_contract():
    connector = _DummyConnector()
    await assert_connector_returns_valid_jobs(connector, SearchCriteria())
    jobs = await connector.search(SearchCriteria())
    assert jobs[0].source == "dummy"


async def test_contract_helper_rejects_non_job_items():
    """A duck-typed object with the right fields must NOT pass the contract (it is not a Job)."""

    class _DuckConnector(BaseConnector):
        name = "duck"

        async def search(self, criteria: SearchCriteria) -> list:
            return [types.SimpleNamespace(id="1", title="t", company="c", url="u", source="duck")]

    with pytest.raises(AssertionError):
        await assert_connector_returns_valid_jobs(_DuckConnector(), SearchCriteria())
