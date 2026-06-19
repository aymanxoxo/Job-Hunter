"""Pure prompt builders for the AI engine (SDD §5.2)."""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from core.ai_engine.scrub import strip_jobs_for_ai
from core.models.job import Job
from core.models.search_criteria import SearchCriteria


def build_generate_criteria_prompt(profile_text: str) -> str:
    """Build the GENERATE_CRITERIA prompt using the SDD §5.2 contract."""
    return (
        "SYSTEM: You are a career advisor. Given a professional profile, extract a\n"
        "        structured job search criteria object. Respond ONLY with valid JSON.\n"
        "        Schema: { titles: [], keywords: [], exclude_keywords: [],\n"
        "        seniority_levels: [], locations: [] }\n"
        f"USER: {profile_text}"
    )


def build_score_jobs_prompt(criteria: SearchCriteria, jobs: Sequence[Job]) -> str:
    """Build the SCORE_JOBS prompt with criteria JSON and stripped job payloads."""
    criteria_json = _json(_criteria_payload(criteria))
    jobs_json = _json(strip_jobs_for_ai(jobs))
    return (
        "SYSTEM: You are a job match evaluator. Score each job 0-100 against the\n"
        "        criteria. Respond ONLY with a JSON array. Each element:\n"
        "        { id, score, match_reason, red_flags[] }\n"
        f"USER: CRITERIA: {criteria_json}\n"
        f"      JOBS: {jobs_json}"
    )


def _criteria_payload(criteria: SearchCriteria) -> dict[str, tuple[str, ...]]:
    return {
        "titles": criteria.titles,
        "keywords": criteria.keywords,
        "exclude_keywords": criteria.exclude_keywords,
        "seniority_levels": criteria.seniority_levels,
        "locations": criteria.locations,
    }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
