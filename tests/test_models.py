"""C-004 — Job and SearchCriteria data models (SDD §3)."""
import pytest
from pydantic import ValidationError

from core.models import Job, SearchCriteria
from core.models.search_criteria import DEFAULT_MAX_RESULTS, DEFAULT_MIN_SCORE

FROZEN = (ValidationError, TypeError)


def _job(**over):
    base = dict(id="1", title="Dev", company="Acme", url="https://x", source="mock")
    base.update(over)
    return Job(**base)


def test_job_requires_core_fields():
    with pytest.raises(ValidationError):
        Job(id="1", title="Dev", company="Acme")  # missing url + source


def test_job_optional_defaults():
    j = _job()
    assert j.location is None and j.description is None and j.score is None
    assert j.red_flags == []


def test_job_is_frozen():
    j = _job()
    with pytest.raises(FROZEN):
        j.title = "Other"


def test_job_score_must_be_0_to_100():
    assert _job(score=0).score == 0
    assert _job(score=100).score == 100
    with pytest.raises(ValidationError):
        _job(score=101)
    with pytest.raises(ValidationError):
        _job(score=-1)


def test_job_scoring_does_not_mutate_input():
    j = _job()
    scored = j.model_copy(update={"score": 90, "match_reason": "good"})
    assert scored.score == 90 and scored.match_reason == "good"
    assert j.score is None


def test_criteria_defaults():
    c = SearchCriteria()
    assert c.titles == [] and c.keywords == [] and c.exclude_keywords == []
    assert c.min_score_threshold == DEFAULT_MIN_SCORE == 40
    assert c.max_results == DEFAULT_MAX_RESULTS == 50
    assert c.date_posted_days is None and c.raw_profile is None


def test_criteria_accepts_values_and_is_frozen():
    c = SearchCriteria(titles=["DevOps Lead"], keywords=["k8s"], min_score_threshold=70)
    assert c.titles == ["DevOps Lead"] and c.min_score_threshold == 70
    with pytest.raises(FROZEN):
        c.titles = ["x"]


def test_criteria_bounds():
    with pytest.raises(ValidationError):
        SearchCriteria(min_score_threshold=101)
    with pytest.raises(ValidationError):
        SearchCriteria(max_results=0)
    with pytest.raises(ValidationError):
        SearchCriteria(date_posted_days=0)
