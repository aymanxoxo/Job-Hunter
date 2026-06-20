# Profile Input Authoring Guide

A profile input parser converts a source, such as pasted text or a future file upload, into plain
profile text before criteria generation. Profile inputs can be built in under `core/profile_inputs/`
or dropped into the user `profile_inputs/` directory.

## Contract

Every parser must inherit `BaseProfileInput`:

```python
from core.profile_inputs.base_profile_input import BaseProfileInput


class MarkdownProfileInput(BaseProfileInput):
    name = "markdown"
    accepts = ("md", "markdown")

    async def to_text(self, source: object) -> str:
        if not isinstance(source, str):
            raise TypeError("MarkdownProfileInput expects text source")
        return source
```

Required class attributes:

- `name`: selected by `config.yaml` under `profile.input`.
- `accepts`: source labels or extensions handled by the parser.

Required method:

- `async def to_text(source: object) -> str`

The output must be plain text suitable for AI criteria generation.

## Discovery

Discovery scans direct `*.py` files only:

- Built-ins: `core/profile_inputs/`
- User drop-zone: `profile_inputs/`

Files starting with `_` or `base_` are skipped. No registration file is needed.

## Config

Select the input parser in `config.yaml`:

```yaml
profile:
  input: markdown
```

The current CLI primarily passes text into the runner. File-oriented parsers should still be written
behind the `BaseProfileInput` contract so desktop and future CLI file flows can reuse them.

## Error Handling

Raise clear `TypeError` or parser-specific errors when the source type is unsupported or the file is
unreadable. Do not log raw CV text unless a user explicitly opts into debug output.

For binary formats, keep extraction deterministic in tests by using small fixtures.

## Tests

Add a focused test file such as `tests/test_markdown_profile_input.py`.

At minimum, cover:

- Metadata: `name` and `accepts`.
- A valid source converts to plain text.
- Invalid source types fail clearly.
- The returned value is a `str`.

Run:

```bash
python -m pytest tests/test_markdown_profile_input.py -q --asyncio-mode=auto
python tools/jh.py gate C-XXX
```

## Checklist

- The class inherits `BaseProfileInput`.
- `to_text` returns plain text and does not mutate source objects.
- The parser has deterministic focused tests.
- Large or sensitive raw profile data is not logged.
- `profile.input` documentation is updated if the parser is built in.
