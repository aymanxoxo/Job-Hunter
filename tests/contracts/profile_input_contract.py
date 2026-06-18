"""Reusable assertions for profile input plugins."""
from __future__ import annotations

from core.profile_inputs import BaseProfileInput


async def assert_profile_input_returns_text(
    profile_input: BaseProfileInput,
    source: object,
    *,
    expected: str | None = None,
) -> str:
    """Assert a profile input normalizes its source to plain text."""

    text = await profile_input.to_text(source)
    assert isinstance(text, str), "Profile input must return a plain str"
    if expected is not None:
        assert text == expected
    return text
