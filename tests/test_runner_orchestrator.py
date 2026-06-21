"""C-025 - runner orchestrator: full pipeline wiring (SDD §5.1)."""
from __future__ import annotations

import io
import json
from datetime import datetime
from types import SimpleNamespace

from core.ai_providers import BaseAIProvider
from core.connectors import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from core.progress import ProgressEmitter
from core.runner import Runner, RunResult, build_runner


def _job(jid: str, url: str, score: int | None = None) -> Job:
    return Job(id=jid, title="Dev", company="Acme", url=url, source="mock", score=score)


class StubProvider(BaseAIProvider):
    name = "stub"
    auth_methods = ("none",)

    async def generate_criteria(self, profile):
        return SearchCriteria(raw_profile=profile, min_score_threshold=50)

    async def score_jobs(self, jobs, criteria):
        return [job.model_copy(update={"score": 90 if "good" in job.url else 10}) for job in jobs]


class FakeConnector(BaseConnector):
    name = "fake"
    auth_methods = ("none",)

    def __init__(self, jobs):
        self._jobs = list(jobs)

    async def search(self, criteria):
        return list(self._jobs)


class BoomConnector(BaseConnector):
    name = "boom"

    async def search(self, criteria):
        raise RuntimeError("connector down")


def _runner(connectors, **kw):
    stream = io.StringIO()
    runner = Runner(
        provider=StubProvider(),
        connectors=connectors,
        emitter=ProgressEmitter(stream=stream),
        clock=lambda: datetime(2026, 6, 20, 1, 2, 3),
        run_id="rid1",
        **kw,
    )
    return runner, stream


async def test_run_full_pipeline_dedup_score_filter_sort_export(tmp_path):
    good = _job("1", "https://good/1")
    dupe = _job("3", "https://good/1")
    bad = _job("2", "https://bad/2")
    runner, stream = _runner(
        [FakeConnector([good, dupe]), FakeConnector([bad])],
        output_dir=tmp_path,
        output_format="json",
    )

    result = await runner.run("a good python profile")

    assert isinstance(result, RunResult)
    assert [job.id for job in result.jobs] == ["1"]   # dupe deduped, bad below threshold 50
    assert result.jobs[0].score == 90
    assert result.exported[0].exists()
    stages = [json.loads(line)["stage"] for line in stream.getvalue().splitlines()]
    assert stages[0] == "profile" and "search" in stages and stages[-1] == "export"


async def test_run_is_fail_graceful_per_connector(tmp_path):
    good = _job("1", "https://good/1")
    runner, _ = _runner(
        [BoomConnector(), FakeConnector([good])], output_dir=tmp_path, output_format="json"
    )

    result = await runner.run("good profile")

    assert [job.id for job in result.jobs] == ["1"]   # boom isolated; good still flows


async def test_run_with_no_results_exports_empty(tmp_path):
    runner, _ = _runner([FakeConnector([])], output_dir=tmp_path, output_format="json")
    result = await runner.run("profile")
    assert result.jobs == ()
    assert result.exported[0].exists()


def test_build_runner_selects_provider_by_name_and_instantiates_connectors():
    class Alpha(BaseAIProvider):
        name = "alpha"

        def __init__(self, **_kw) -> None:
            pass

        async def generate_criteria(self, profile):
            return SearchCriteria(raw_profile=profile)

        async def score_jobs(self, jobs, criteria):
            return jobs

    class C1(BaseConnector):
        name = "c1"

        async def search(self, criteria):
            return []

    def fake_discover(directory, base):
        if base is BaseAIProvider and "ai_providers" in str(directory):
            return [Alpha]
        if base is BaseConnector and "connectors" in str(directory):
            return [C1]
        return []

    config = SimpleNamespace(
        ai=SimpleNamespace(provider="alpha", model="x", batch_size=10),
        connectors={},
        output=SimpleNamespace(directory="output/", format="both"),
    )
    runner = build_runner(config, discover=fake_discover)

    assert isinstance(runner.provider, Alpha)
    assert [type(connector) for connector in runner.connectors] == [C1]
