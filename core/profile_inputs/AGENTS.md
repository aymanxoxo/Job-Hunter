# core/profile_inputs - profile source normalization

## Contents
- `base_profile_input.py` - `BaseProfileInput` ABC: async `to_text(source) -> str`.
- `text_input.py` - `TextProfileInput`, the v1 built-in text passthrough parser.
- `__init__.py` - exports `BaseProfileInput` and `TextProfileInput`.

## Contracts
- Profile inputs normalize a supported source to plain text before criteria generation.
- `accepts` is a tuple of source type identifiers such as `("text",)` or future file types.
- `TextProfileInput` accepts only `str` and preserves it unchanged.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- SDD: [../../Documents/JobHunter_SDD_v1.1.md](../../Documents/JobHunter_SDD_v1.1.md) §5.3
- Decision: [../../Documents/DECISIONS.md](../../Documents/DECISIONS.md) ADR-005
