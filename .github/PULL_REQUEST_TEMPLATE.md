## Chunk
C-XXX — <title>

## Design note (technical)
- Goal / contract:
- Signatures / types added:
- Pure vs effect split:
- External APIs used (verified to exist):
- Decisions (→ ADR if cross-cutting):

## Business value / rules — if any (ADR-017)
- User / product value:
- Business rules encoded:
- Added to `Documents/PRODUCT_NOTES.md`? (+ `docs/business/<topic>.md` if substantial):

## Docs updated (ADR-017)
- Module `AGENTS.md`:
- `docs/tech/<topic>.md` (only if non-obvious / cross-cutting):

## Test evidence (paste real output)
- Red (tests fail first):
- Green (chunk tests pass):
- Full gate (`python tools/jh.py gate C-XXX`, including full suite + ruff):

## Definition of Done (plan §3.1)
- [ ] Chunk tests green
- [ ] Full `pytest` green
- [ ] `ruff` clean
- [ ] FP + logging conventions (stderr-only logs, `run_id`)
- [ ] Only this chunk's scope touched
- [ ] Docs synced — PROGRESS ledger + tech (`AGENTS.md`) + business (`PRODUCT_NOTES.md`) where warranted
- [ ] One commit on `chunk/C-XXX`, `[C-XXX]` message

## Risk read
<low / medium / high + recommendation>
