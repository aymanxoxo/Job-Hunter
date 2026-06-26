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


class AuthFailConnector(BaseConnector):
    name = "authfail"

    async def authenticate(self):
        return False

    async def search(self, criteria):
        raise AssertionError("search must not run after failed auth")


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


async def test_run_emits_connector_level_search_progress(tmp_path):
    runner, stream = _runner(
        [FakeConnector([]), BoomConnector(), AuthFailConnector()],
        output_dir=tmp_path,
        output_format="json",
    )

    result = await runner.run("profile")

    assert result.jobs == ()
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    connector_events = [
        event
        for event in events
        if event["stage"] == "search" and event.get("connector") is not None
    ]

    assert {
        (event["connector"], event["state"], event.get("message"), event["metric"]["jobs"])
        for event in connector_events
        if event["state"] != "active"
    } == {
        ("fake", "done", "0 results", 0),
        ("boom", "failed", "connector failed", 0),
        ("authfail", "failed", "authentication failed", 0),
    }
    search_done = [
        event for event in events if event["stage"] == "search" and event["state"] == "done"
    ][-1]
    assert search_done["metric"] == {"jobs": 0}
    assert search_done["current"] == 3
    assert search_done["total"] == 3


async def test_run_with_no_results_exports_empty(tmp_path):
    runner, _ = _runner([FakeConnector([])], output_dir=tmp_path, output_format="json")
    result = await runner.run("profile")
    assert result.jobs == ()
    assert result.exported[0].exists()


async def test_run_is_fail_graceful_when_score_jobs_raises(tmp_path):
    """score_jobs raising must not abort the run — pipeline completes with unscored results."""
    good = _job("1", "https://example.com/1")

    class BoomProvider(BaseAIProvider):
        name = "boom"
        auth_methods = ("none",)

        async def generate_criteria(self, profile):
            return SearchCriteria(raw_profile=profile, min_score_threshold=0)

        async def score_jobs(self, jobs, criteria):
            raise RuntimeError("AI service down")

    runner, _ = _runner(
        [FakeConnector([good])],
        output_dir=tmp_path,
        output_format="json",
    )
    runner.provider = BoomProvider()

    result = await runner.run("profile")

    # Run must complete (not raise) and export a file even though scoring failed.
    assert isinstance(result, RunResult)
    assert result.exported[0].exists()
    # C-072: the scraped job must stay visible (unscored) rather than being filtered to empty.
    assert [job.id for job in result.jobs] == ["1"]
    assert result.jobs[0].score is None


async def test_run_keeps_unscored_jobs_visible_on_provider_failure(tmp_path):
    """C-072: when scoring fails wholesale, all scraped jobs stay visible despite the threshold.

    Without the fallback, ``filter_below_threshold`` drops every ``score is None`` job, so a
    provider outage would silently empty the results even though connectors found listings.
    """
    a = _job("1", "https://example.com/1")
    b = _job("2", "https://example.com/2")
    c = _job("3", "https://example.com/3")

    class DownProvider(BaseAIProvider):
        name = "down"
        auth_methods = ("none",)

        async def generate_criteria(self, profile):
            # Non-zero threshold: would filter out every unscored job if applied.
            return SearchCriteria(raw_profile=profile, min_score_threshold=50)

        async def score_jobs(self, jobs, criteria):
            raise RuntimeError("AI service down")

    runner, _ = _runner(
        [FakeConnector([a, b, c])],
        output_dir=tmp_path,
        output_format="json",
    )
    runner.provider = DownProvider()
    logs: list[dict] = []
    original_warning = runner.log.warning

    def capture_warning(msg, **kwargs):
        logs.append({"msg": msg, **kwargs})
        original_warning(msg, **kwargs)

    runner.log.warning = capture_warning  # type: ignore[method-assign]

    result = await runner.run("profile")

    # All three scraped jobs survive, in input order, unscored.
    assert [job.id for job in result.jobs] == ["1", "2", "3"]
    assert all(job.score is None for job in result.jobs)
    # The failure path warns about both the provider error and the unfiltered fallback.
    assert any("score_jobs failed" in log.get("msg", "") for log in logs)
    fallback = [log for log in logs if "unscored" in log.get("msg", "").lower()
                and "unavailable" in log.get("msg", "").lower()]
    assert len(fallback) == 1
    assert fallback[0].get("count") == 3
    # The misleading "excluded" warning from the success path must NOT fire on provider failure.
    assert not any("excluded" in log.get("msg", "").lower() for log in logs)


async def test_run_wires_min_score_threshold_from_config(tmp_path):
    """Runner should override generated criteria's min_score_threshold with the config value."""
    good = _job("1", "https://good/1")
    runner, _ = _runner(
        [FakeConnector([good])],
        output_dir=tmp_path,
        output_format="json",
    )
    runner.min_score_threshold = 80  # config says 80, provider generates 50

    result = await runner.run("profile")

    # Provider generated criteria with threshold 50, but runner should override to 80.
    # Since the job scores 90 (above 80), it should be kept.
    assert result.criteria.min_score_threshold == 80
    assert [job.id for job in result.jobs] == ["1"]


async def test_run_filters_unscored_jobs_and_logs_warning(tmp_path):
    """Jobs that remain unscored after scoring should be visible in structured logs."""
    unscored = _job("1", "https://unscored/1")
    scored = _job("2", "https://scored/2")

    class PartialProvider(BaseAIProvider):
        name = "partial"
        auth_methods = ("none",)

        async def generate_criteria(self, profile):
            return SearchCriteria(raw_profile=profile, min_score_threshold=0)

        async def score_jobs(self, jobs, criteria):
            # Only score the second job
            return [job.model_copy(update={"score": 90}) if job.id == "2" else job for job in jobs]

    runner, _ = _runner(
        [FakeConnector([unscored, scored])],
        output_dir=tmp_path,
        output_format="json",
    )
    runner.provider = PartialProvider()
    logs: list[dict] = []
    original_warning = runner.log.warning

    def capture_warning(msg, **kwargs):
        logs.append({"msg": msg, **kwargs})
        original_warning(msg, **kwargs)

    runner.log.warning = capture_warning  # type: ignore[method-assign]

    result = await runner.run("profile")

    assert [job.id for job in result.jobs] == ["2"]
    # Unscored job should be logged
    unscored_logs = [log for log in logs if "unscored" in log.get("msg", "").lower()]
    assert len(unscored_logs) >= 1
    assert unscored_logs[0].get("count", 0) == 1


async def test_run_wires_min_score_threshold_zero(tmp_path):
    """Runner should override generated criteria with min_score_threshold=0 (falsy but valid)."""
    good = _job("1", "https://good/1")
    runner, _ = _runner(
        [FakeConnector([good])],
        output_dir=tmp_path,
        output_format="json",
    )
    runner.min_score_threshold = 0  # falsy but valid; must still override

    result = await runner.run("profile")

    assert result.criteria.min_score_threshold == 0
    assert [job.id for job in result.jobs] == ["1"]


async def test_run_no_unscored_jobs_no_warning(tmp_path):
    """When all jobs are scored, no unscored warning should be logged."""
    scored = _job("1", "https://good/1")
    runner, _ = _runner(
        [FakeConnector([scored])],
        output_dir=tmp_path,
        output_format="json",
    )
    logs: list[dict] = []
    original_warning = runner.log.warning

    def capture_warning(msg, **kwargs):
        logs.append({"msg": msg, **kwargs})
        original_warning(msg, **kwargs)

    runner.log.warning = capture_warning  # type: ignore[method-assign]

    result = await runner.run("profile")

    assert [job.id for job in result.jobs] == ["1"]
    unscored_logs = [log for log in logs if "unscored" in log.get("msg", "").lower()]
    assert len(unscored_logs) == 0


async def test_search_all_skips_connectors_with_enabled_false(tmp_path):
    """Connectors that have enabled=False on themselves must be excluded from search."""
    searched: list[str] = []

    class TrackingConnector(BaseConnector):
        name = "tracking"
        auth_methods = ("none",)

        def __init__(self, *, enabled: bool = True, jobs=None):
            self.enabled = enabled
            self._jobs = jobs or []

        async def search(self, criteria):
            searched.append(self.name)
            return list(self._jobs)

    disabled = TrackingConnector(enabled=False)
    active = TrackingConnector(enabled=True, jobs=[_job("1", "https://x.com/1")])
    runner, _ = _runner([disabled, active], output_dir=tmp_path, output_format="json")

    await runner.run("profile")

    assert searched == ["tracking"]  # only the enabled one was searched


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
