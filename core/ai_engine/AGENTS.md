# core/ai_engine - pure AI engine helpers

## Contents
- `prompts.py` - deterministic GENERATE_CRITERIA and SCORE_JOBS prompt builders.
- `__init__.py` - exports currently landed AI-engine helpers.

## Contracts
- Prompt builders are pure: no provider calls, config reads, logging, network, or filesystem effects.
- `build_generate_criteria_prompt()` preserves profile text verbatim after the `USER:` prefix.
- `build_score_jobs_prompt()` emits compact deterministic JSON for structured criteria and only sends job `id`, `title`, `company`, and `description`.
- Response parsing, reusable job scrubbing, batching, and the provider facade land in later chunks.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Spec: `../../Documents/JobHunter_SDD_v1.1.md` §5.2
