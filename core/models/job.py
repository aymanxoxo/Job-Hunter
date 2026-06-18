"""The Job data model (SDD §3.1).

Immutable (``frozen``): connectors build a Job with what they can, and the AI engine produces a
*new* scored copy via ``model_copy`` rather than mutating the original (SDD §5.2).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Job(BaseModel):
    """A single job posting; required fields always present, the rest connector-dependent."""

    model_config = ConfigDict(frozen=True)

    # Required — every connector must supply these.
    id: str
    title: str
    company: str
    url: str
    source: str

    # Optional — connectors fill what the source provides.
    location: str | None = None
    description: str | None = None
    salary_range: str | None = None
    posted_date: datetime | None = None

    # AI-populated by the scoring engine.
    score: int | None = Field(default=None, ge=0, le=100)
    match_reason: str | None = None
    red_flags: list[str] = Field(default_factory=list)

    # Original scraped payload, for debugging only.
    raw: dict | None = None
