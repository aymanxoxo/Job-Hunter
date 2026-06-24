# core/ai_engine - AI facade and pure helpers

## Contents
- `prompts.py` - deterministic GENERATE_CRITERIA and SCORE_JOBS prompt builders.
- `parsing.py` - pure parsers for criteria JSON and scored-job JSON responses.
- `scrub.py` - pure job field-stripper for SCORE_JOBS provider payloads.
- `batching.py` - pure order-preserving batching utility for scoring calls.
- `__init__.py` - async `AIEngine` facade plus module-level helper exports.

## Contracts
- `AIEngine` is the thin imperative shell: it calls an injected async prompt provider and returns
  validated JobHunter models.
- `generate_criteria()` builds the SDD GENERATE_CRITERIA prompt, parses provider JSON, and preserves
  the source profile on `SearchCriteria.raw_profile`.
- `score_jobs()` splits work with `batch_items()`, sends only scrubbed job payloads through the prompt
  builder, and returns scored `Job` copies without mutating input jobs.
- Malformed top-level provider output raises `AIEngineError`; malformed scored-job items are skipped so
  the rest of a batch can still be returned.
- Prompt builders are pure: no provider calls, config reads, logging, network, or filesystem effects.
- `build_generate_criteria_prompt()` preserves profile text verbatim after the `USER:` prefix.
- `build_score_jobs_prompt()` emits compact deterministic JSON for structured criteria and only sends job
  `id`, `title`, `company`, and `description`.
- `parse_criteria_response()` returns a model on valid JSON and `None` on malformed/invalid provider
  output. `parse_scored_jobs_response()` returns scored copies for valid items, preserves jobs with no
  valid score row, and returns `None` only when the top-level response is not a JSON list.
- `strip_job_for_ai()` and `strip_jobs_for_ai()` keep only job `id`, `title`, `company`, and
  `description` before any provider call.
- `batch_items()` splits sequences into list batches and rejects `batch_size < 1`.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Spec: `../../Documents/JobHunter_SDD_v1.1.md` section 5.2
