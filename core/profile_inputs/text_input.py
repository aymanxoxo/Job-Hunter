"""Built-in text profile input for v1."""
from __future__ import annotations

from core.profile_inputs.base_profile_input import BaseProfileInput


class TextProfileInput(BaseProfileInput):
    """Pass plain text profile input through unchanged."""

    name = "text"
    accepts = ("text",)

    async def to_text(self, source: object) -> str:
        if not isinstance(source, str):
            raise TypeError("TextProfileInput expects source to be str")
        return source
