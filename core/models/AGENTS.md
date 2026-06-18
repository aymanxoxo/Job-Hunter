# core/models — data models

Immutable (`frozen`) pydantic v2 models — the shared vocabulary passed through the pipeline. Pure
data; no I/O. Re-exported so `from core.models import Job, SearchCriteria` works.

## Contents
- `job.py` — `Job`: one posting. **Required**: id, title, company, url, source. **Optional**:
  location, description, salary_range, posted_date. **AI-populated**: score (0–100), match_reason,
  red_flags. Plus `raw` (debug). Frozen → the scorer returns `model_copy(update=...)`, never mutates.
- `search_criteria.py` — `SearchCriteria`: titles / keywords / exclude_keywords / seniority_levels /
  locations + `min_score_threshold` (default 40 — the single effective filter, ADR-006),
  `max_results` (50), `date_posted_days`, `raw_profile`. Constants: `DEFAULT_MIN_SCORE`,
  `DEFAULT_MAX_RESULTS`.

## Conventions
- Frozen + validated (score 0–100; max_results ≥ 1; date_posted_days ≥ 1).

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md) · Spec: SDD §3 · Filter rule: ADR-006.
