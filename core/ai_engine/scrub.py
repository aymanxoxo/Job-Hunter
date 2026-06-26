"""Pure job payload scrubbing before AI provider calls (SDD §5.2 IMPORTANT)."""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from core.models.job import Job

# Role markers the SCORE_JOBS prompt uses to separate instructions from data. Job descriptions come
# from arbitrary web pages, so a posting could embed these to try to hijack scoring; defang them.
_ROLE_MARKER_RE = re.compile(r"(?i)\b(system|user|assistant)\s*:")
# C0 control chars (except tab/newline/carriage-return) carry no meaning in a description.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def neutralize_prompt_text(value: str | None) -> str | None:
    """Strip control chars and defang prompt role markers in untrusted free text (pure)."""
    if value is None:
        return None
    cleaned = _CONTROL_CHAR_RE.sub("", value)
    return _ROLE_MARKER_RE.sub(lambda m: m.group(1), cleaned)


def strip_job_for_ai(job: Job) -> dict[str, Any]:
    """Return only the fields allowed in SCORE_JOBS provider payloads."""
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "description": neutralize_prompt_text(job.description),
    }


def strip_jobs_for_ai(jobs: Sequence[Job]) -> list[dict[str, Any]]:
    """Strip a sequence of jobs while preserving order."""
    return [strip_job_for_ai(job) for job in jobs]
