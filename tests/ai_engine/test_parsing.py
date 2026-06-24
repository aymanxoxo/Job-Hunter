"""C-011 - pure AI response parsers."""
from __future__ import annotations

from core.ai_engine.parsing import parse_criteria_response, parse_scored_jobs_response
from core.models.job import Job


def _job(**overrides):
    data = {
        "id": "job-1",
        "title": "Python Developer",
        "company": "Acme",
        "url": "https://example.invalid/job-1",
        "source": "mock",
    }
    data.update(overrides)
    return Job(**data)


def test_parse_criteria_response_returns_search_criteria():
    criteria = parse_criteria_response(
        """
        {
          "titles": ["Python Developer"],
          "keywords": ["python", "api"],
          "exclude_keywords": ["manager"],
          "seniority_levels": ["senior"],
          "locations": ["remote"]
        }
        """,
        raw_profile="profile text",
    )

    assert criteria is not None
    assert criteria.titles == ("Python Developer",)
    assert criteria.keywords == ("python", "api")
    assert criteria.exclude_keywords == ("manager",)
    assert criteria.seniority_levels == ("senior",)
    assert criteria.locations == ("remote",)
    assert criteria.raw_profile == "profile text"


def test_parse_criteria_response_ignores_unknown_fields():
    criteria = parse_criteria_response(
        '{"titles":["Dev"],"keywords":[],"exclude_keywords":[],"seniority_levels":[],"locations":[],"extra":"ignored"}'
    )

    assert criteria is not None
    assert criteria.titles == ("Dev",)


def test_parse_criteria_response_returns_none_for_malformed_or_invalid_json():
    assert parse_criteria_response("not json") is None
    assert parse_criteria_response("[]") is None
    assert parse_criteria_response('{"titles": "not-a-list"}') is None


def test_parse_scored_jobs_response_applies_scores_without_mutating_inputs():
    original = _job()

    scored = parse_scored_jobs_response(
        """
        [
          {
            "id": "job-1",
            "score": 91,
            "match_reason": "Strong Python API match",
            "red_flags": ["none"]
          }
        ]
        """,
        [original],
    )

    assert scored is not None
    assert scored[0].id == "job-1"
    assert scored[0].score == 91
    assert scored[0].match_reason == "Strong Python API match"
    assert scored[0].red_flags == ("none",)
    assert original.score is None
    assert scored[0] is not original


def test_parse_scored_jobs_response_preserves_unmentioned_jobs():
    first = _job(id="job-1")
    second = _job(id="job-2", url="https://example.invalid/job-2")

    scored = parse_scored_jobs_response(
        '[{"id":"job-1","score":80,"match_reason":"ok","red_flags":[]}]',
        [first, second],
    )

    assert scored is not None
    assert [job.id for job in scored] == ["job-1", "job-2"]
    assert scored[0].score == 80
    assert scored[1] == second


def test_parse_scored_jobs_response_skips_malformed_items_and_preserves_jobs():
    first = _job(id="job-1")
    second = _job(id="job-2", url="https://example.invalid/job-2")

    scored = parse_scored_jobs_response(
        """
        [
          {"id":"job-1","score":101,"match_reason":"too high","red_flags":[]},
          {"id":"job-2","score":81,"match_reason":"valid","red_flags":[]},
          {"id":"job-3","score":80}
        ]
        """,
        [first, second],
    )

    assert scored is not None
    assert scored[0] == first
    assert scored[1].score == 81
    assert scored[1].match_reason == "valid"


def test_parse_scored_jobs_response_returns_none_for_malformed_top_level_input():
    jobs = [_job()]

    assert parse_scored_jobs_response("not json", jobs) is None
    assert parse_scored_jobs_response("{}", jobs) is None


def test_parse_scored_jobs_response_returns_none_when_all_items_malformed():
    jobs = [_job()]

    assert parse_scored_jobs_response('[{"bad": true}]', jobs) is None


def test_parse_scored_jobs_response_ignores_unknown_job_ids():
    original = _job()

    scored = parse_scored_jobs_response(
        '[{"id":"missing","score":20,"match_reason":"no","red_flags":["wrong"]}]',
        [original],
    )

    assert scored == [original]
