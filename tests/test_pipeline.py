"""C-022 - pure pipeline transforms."""
from __future__ import annotations

from core.models.job import Job
from core.pipeline import dedup_by_url, filter_below_threshold, merge_results, sort_by_score


def _job(**overrides) -> Job:
    data = {
        "id": "job-1",
        "title": "Python Developer",
        "company": "Acme",
        "url": "https://example.invalid/job-1",
        "source": "mock",
    }
    data.update(overrides)
    return Job(**data)


def test_merge_results_flattens_connector_results_in_order():
    first = _job(id="1", url="https://example.invalid/1", source="mock")
    second = _job(id="2", url="https://example.invalid/2", source="indeed")
    third = _job(id="3", url="https://example.invalid/3", source="linkedin")

    merged = merge_results([[first, second], [], [third]])

    assert merged == [first, second, third]


def test_dedup_by_url_keeps_first_job_for_each_url():
    first = _job(id="first", url="https://example.invalid/shared", source="mock")
    duplicate = _job(id="duplicate", url="https://example.invalid/shared", source="indeed")
    unique = _job(id="unique", url="https://example.invalid/unique", source="linkedin")

    deduped = dedup_by_url([first, duplicate, unique])

    assert deduped == [first, unique]


def test_dedup_by_url_preserves_order_and_does_not_mutate_inputs():
    jobs = [
        _job(id="1", url="https://example.invalid/1"),
        _job(id="2", url="https://example.invalid/2"),
    ]
    original = tuple(jobs)

    deduped = dedup_by_url(jobs)

    assert deduped == jobs
    assert jobs == list(original)
    assert deduped[0] is jobs[0]


def test_sort_by_score_descending_treats_unscored_as_zero_and_is_stable():
    high = _job(id="high", url="https://example.invalid/high", score=90)
    tie_first = _job(id="tie-1", url="https://example.invalid/tie-1", score=70)
    tie_second = _job(id="tie-2", url="https://example.invalid/tie-2", score=70)
    unscored = _job(id="unscored", url="https://example.invalid/unscored", score=None)

    sorted_jobs = sort_by_score([tie_first, unscored, high, tie_second])

    assert [job.id for job in sorted_jobs] == ["high", "tie-1", "tie-2", "unscored"]


def test_filter_below_threshold_keeps_jobs_at_or_above_threshold():
    below = _job(id="below", url="https://example.invalid/below", score=39)
    exact = _job(id="exact", url="https://example.invalid/exact", score=40)
    high = _job(id="high", url="https://example.invalid/high", score=90)

    kept = filter_below_threshold([below, exact, high], min_score_threshold=40)

    assert [job.id for job in kept] == ["exact", "high"]


def test_filter_below_threshold_excludes_unscored_jobs():
    unscored = _job(id="unscored", url="https://example.invalid/unscored", score=None)
    scored = _job(id="scored", url="https://example.invalid/scored", score=1)

    kept = filter_below_threshold([unscored, scored], min_score_threshold=1)

    assert kept == [scored]


def test_transforms_compose_for_pipeline_steps_8_to_10():
    duplicate_low = _job(id="duplicate-low", url="https://example.invalid/shared", score=20)
    duplicate_high = _job(id="duplicate-high", url="https://example.invalid/shared", score=95)
    unique = _job(id="unique", url="https://example.invalid/unique", score=80)

    merged = merge_results([[duplicate_low], [duplicate_high, unique]])
    final = sort_by_score(filter_below_threshold(dedup_by_url(merged), min_score_threshold=40))

    assert [job.id for job in final] == ["unique"]
