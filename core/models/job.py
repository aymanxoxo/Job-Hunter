"""The Job data model (SDD §3.1).

Immutable (``frozen`` + tuple containers): connectors build a Job with what they can, and the AI
engine produces a *new* scored copy via ``model_copy`` rather than mutating the original (SDD §5.2).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Job(BaseModel):
    """A single job posting; required fields always present, the rest connector-dependent."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    company: str
    url: str
    source: str

    location: str | None = None
    description: str | None = None
    salary_range: str | None = None
    posted_date: datetime | None = None

    score: int | None = Field(default=None, ge=0, le=100)
    match_reason: str | None = None
    red_flags: tuple[str, ...] = ()

    raw: dict | None = None
