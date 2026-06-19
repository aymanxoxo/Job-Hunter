"""The Job data model (SDD §3.1).

Immutable (``frozen`` + tuple containers): connectors build a Job with what they can, and the AI
engine produces a *new* scored copy via ``model_copy`` rather than mutating the original (SDD §5.2).
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


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

    raw: Mapping[str, Any] | None = None

    @field_validator("raw", mode="after")
    @classmethod
    def _freeze_raw(cls, value: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
        return None if value is None else MappingProxyType(dict(value))

    @field_serializer("raw")
    def _serialize_raw(self, value: Mapping[str, Any] | None) -> dict[str, Any] | None:
        return None if value is None else dict(value)
