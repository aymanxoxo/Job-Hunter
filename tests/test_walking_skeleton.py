"""C-039 - walking skeleton smoke coverage."""
from __future__ import annotations

import json
from pathlib import Path

from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from core.walking_skeleton import FixtureConnector, StubAIProvider, run_walking_skeleton


def _fixture_path(tmp_path: Path) -> Path:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "remote-python",
                    "title": "Senior Python Developer",
                    "company": "Acme",
                    "url": "https://example.test/jobs/remote-python",
                    "source": "fixture",
                    "location": "Remote",
                    "description": "Build Python services with async APIs.",
                },
                {
                    "id": "office-data",
                    "title": "Data Analyst",
                    "company": "Beta",
                    "url": "https://example.test/jobs/office-data",
                    "source": "fixture",
                    "location": "Cairo",
                    "description": "Spreadsheet-heavy reporting role.",
                },
            ]
        ),
        encoding="utf-8",
    )
    return path


async def test_stub_provider_generates_criteria_from_profile_text():
    provider = StubAIProvider()

    criteria = await provider.generate_criteria("Senior Python developer seeking remote work")

    assert criteria == SearchCriteria(
        titles=("Senior Python Developer",),
        keywords=("python", "developer", "remote"),
        locations=("remote",),
        raw_profile="Senior Python developer seeking remote work",
    )


async def test_fixture_connector_loads_jobs_matching_generated_criteria(tmp_path: Path):
    connector = FixtureConnector(_fixture_path(tmp_path))
    criteria = SearchCriteria(keywords=("python", "remote"))

    jobs = await connector.search(criteria)

    assert [job.id for job in jobs] == ["remote-python"]
    assert all(isinstance(job, Job) for job in jobs)


async def test_walking_skeleton_runs_profile_to_scored_export(tmp_path: Path):
    output_path = tmp_path / "results.json"

    result = await run_walking_skeleton(
        "Senior Python developer seeking remote work",
        fixture_path=_fixture_path(tmp_path),
        output_path=output_path,
    )

    assert result.criteria.keywords == ("python", "developer", "remote")
    assert [job.id for job in result.jobs] == ["remote-python"]
    assert result.jobs[0].score is not None
    assert result.jobs[0].match_reason == "Matched: python, remote"

    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["criteria"]["raw_profile"] == "Senior Python developer seeking remote work"
    assert exported["jobs"][0]["id"] == "remote-python"
    assert exported["jobs"][0]["score"] == result.jobs[0].score
