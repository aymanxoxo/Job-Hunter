"""The SearchCriteria data model (SDD §3.2).

Produced by the AI engine from a profile, or edited by the user. Immutable (``frozen`` + tuple
containers). ``min_score_threshold`` defaults to ``DEFAULT_MIN_SCORE`` and is the single effective
results filter (ADR-006); config only seeds that default at generation time.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MIN_SCORE = 40
DEFAULT_MAX_RESULTS = 50


class SearchCriteria(BaseModel):
    """Structured job-search criteria."""

    model_config = ConfigDict(frozen=True)

    titles: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    seniority_levels: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    min_score_threshold: int = Field(default=DEFAULT_MIN_SCORE, ge=0, le=100)
    max_results: int = Field(default=DEFAULT_MAX_RESULTS, ge=1)
    date_posted_days: int | None = Field(default=None, ge=1)
    raw_profile: str | None = None
