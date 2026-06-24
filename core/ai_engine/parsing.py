"""Pure response parsers for AI provider output (SDD §5.2)."""
from __future__ import annotations

import json
import re as _re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.models.job import Job
from core.models.search_criteria import SearchCriteria

_FENCE_RE = _re.compile(r"```(?:json)?\s*(.*?)\s*```", _re.DOTALL)


class _CriteriaPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    titles: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    seniority_levels: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()


class _ScorePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    score: int = Field(ge=0, le=100)
    match_reason: str
    red_flags: tuple[str, ...] = ()


def parse_criteria_response(text: str, *, raw_profile: str | None = None) -> SearchCriteria | None:
    """Parse a provider's GENERATE_CRITERIA JSON response into ``SearchCriteria``."""
    data = _loads(text)
    if not isinstance(data, dict):
        return None
    try:
        payload = _CriteriaPayload.model_validate(data)
        return SearchCriteria(**payload.model_dump(), raw_profile=raw_profile)
    except ValidationError:
        return None


def parse_scored_jobs_response(text: str, jobs: Sequence[Job]) -> list[Job] | None:
    """Apply a provider's SCORE_JOBS JSON response to immutable ``Job`` copies."""
    data = _loads(text)
    if not isinstance(data, list):
        return None
    scores = []
    for item in data:
        try:
            scores.append(_ScorePayload.model_validate(item))
        except ValidationError:
            continue

    by_id = {score.id: score for score in scores}
    scored_jobs: list[Job] = []
    for job in jobs:
        score = by_id.get(job.id)
        if score is None:
            scored_jobs.append(job)
            continue
        scored_jobs.append(
            job.model_copy(
                update={
                    "score": score.score,
                    "match_reason": score.match_reason,
                    "red_flags": score.red_flags,
                }
            )
        )
    return scored_jobs


def _loads(text: str) -> Any:
    match = _FENCE_RE.search(text)
    candidate = match.group(1) if match else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        try:
            return json.loads(candidate.strip())
        except json.JSONDecodeError:
            return None
