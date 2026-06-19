"""C-013 - pure batching utility."""
from __future__ import annotations

import pytest

from core.ai_engine.batching import batch_items
from core.models.job import Job


def _job(job_id: str) -> Job:
    return Job(
        id=job_id,
        title=f"Job {job_id}",
        company="Acme",
        url=f"https://example.invalid/{job_id}",
        source="mock",
    )


def test_batch_items_returns_empty_for_empty_input():
    assert batch_items([], batch_size=3) == []


def test_batch_items_splits_exact_batches():
    items = [_job("1"), _job("2"), _job("3"), _job("4")]

    batches = batch_items(items, batch_size=2)

    assert [[job.id for job in batch] for batch in batches] == [["1", "2"], ["3", "4"]]


def test_batch_items_splits_remainder_batch():
    items = [_job("1"), _job("2"), _job("3"), _job("4"), _job("5")]

    batches = batch_items(items, batch_size=2)

    assert [[job.id for job in batch] for batch in batches] == [["1", "2"], ["3", "4"], ["5"]]


def test_batch_items_preserves_order_and_does_not_mutate_input():
    items = [_job("1"), _job("2"), _job("3")]
    original = tuple(items)

    batches = batch_items(items, batch_size=2)

    assert items == list(original)
    assert batches[0][0] is items[0]
    assert [job.id for batch in batches for job in batch] == ["1", "2", "3"]


def test_batch_items_accepts_tuples_and_returns_lists():
    items = (_job("1"), _job("2"), _job("3"))

    batches = batch_items(items, batch_size=2)

    assert isinstance(batches, list)
    assert all(isinstance(batch, list) for batch in batches)
    assert [[job.id for job in batch] for batch in batches] == [["1", "2"], ["3"]]


@pytest.mark.parametrize("batch_size", [0, -1])
def test_batch_items_rejects_non_positive_batch_size(batch_size):
    with pytest.raises(ValueError, match="batch_size must be >= 1"):
        batch_items([_job("1")], batch_size=batch_size)
