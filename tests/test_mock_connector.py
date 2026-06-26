"""C-018 - Mock connector and fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.connectors import MockConnector as ExportedMockConnector
from core.connectors.mock_connector import DEFAULT_FIXTURE_PATH, MockConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from tests.contracts.connector_contract import assert_connector_returns_valid_jobs


def _write_fixture(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {
                    "id": "python-remote",
                    "title": "Senior Python Developer",
                    "company": "Acme",
                    "url": "https://example.invalid/python",
                    "source": "fixture",
                    "location": "Remote",
                    "description": "Build async API services.",
                },
                {
                    "id": "data-analyst",
                    "title": "Data Analyst",
                    "company": "Beta",
                    "url": "https://example.invalid/data",
                    "source": "fixture",
                    "location": "Cairo",
                    "description": "Reporting and spreadsheet dashboard work.",
                },
            ]
        ),
        encoding="utf-8",
    )
    return path


async def test_mock_connector_metadata_matches_sdd():
    connector = MockConnector()

    assert connector.name == "mock"
    assert ExportedMockConnector is MockConnector
    assert connector.auth_methods == ("none",)
    assert connector.enabled is True
    assert connector.fixture_path == DEFAULT_FIXTURE_PATH


async def test_default_fixture_loads_valid_mock_jobs():
    connector = MockConnector()

    jobs = await connector.search(SearchCriteria())

    assert jobs
    await assert_connector_returns_valid_jobs(connector, SearchCriteria(keywords=("python",)))
    assert all(isinstance(job, Job) for job in jobs)
    assert all(job.source == "mock" for job in jobs)


async def test_search_filters_by_keyword_in_title_or_description_case_insensitive(tmp_path: Path):
    connector = MockConnector(fixture_path=_write_fixture(tmp_path / "jobs.json"))

    python_jobs = await connector.search(SearchCriteria(keywords=("PYTHON",)))
    api_jobs = await connector.search(SearchCriteria(keywords=("api",)))

    assert [job.id for job in python_jobs] == ["python-remote"]
    assert [job.id for job in api_jobs] == ["python-remote"]


async def test_search_keyword_matching_uses_word_boundaries(tmp_path: Path):
    fixture = tmp_path / "jobs.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "id": "java-role",
                    "title": "Java Developer",
                    "company": "Acme",
                    "url": "https://example.invalid/java",
                    "source": "fixture",
                    "description": "Build backend services.",
                },
                {
                    "id": "javascript-role",
                    "title": "JavaScript Developer",
                    "company": "Beta",
                    "url": "https://example.invalid/javascript",
                    "source": "fixture",
                    "description": "Build web interfaces.",
                },
            ]
        ),
        encoding="utf-8",
    )
    connector = MockConnector(fixture_path=fixture)

    jobs = await connector.search(SearchCriteria(keywords=("java",)))

    assert [job.id for job in jobs] == ["java-role"]


async def test_search_returns_all_jobs_when_no_keywords(tmp_path: Path):
    connector = MockConnector(fixture_path=_write_fixture(tmp_path / "jobs.json"))

    jobs = await connector.search(SearchCriteria())

    assert [job.id for job in jobs] == ["python-remote", "data-analyst"]
    assert all(job.source == "mock" for job in jobs)


async def test_search_returns_jobs_matching_any_keyword_in_fixture_order(tmp_path: Path):
    connector = MockConnector(fixture_path=_write_fixture(tmp_path / "jobs.json"))

    jobs = await connector.search(SearchCriteria(keywords=("dashboard", "python")))

    assert [job.id for job in jobs] == ["python-remote", "data-analyst"]


async def test_search_rejects_non_array_fixture(tmp_path: Path):
    path = tmp_path / "jobs.json"
    path.write_text("{}", encoding="utf-8")
    connector = MockConnector(fixture_path=path)

    with pytest.raises(ValueError, match="JSON array"):
        await connector.search(SearchCriteria())


def test_default_fixture_path_is_absolute():
    """DEFAULT_FIXTURE_PATH must be absolute so MockConnector works regardless of CWD."""
    assert DEFAULT_FIXTURE_PATH.is_absolute()
