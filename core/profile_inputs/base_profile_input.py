"""BaseProfileInput - the plugin contract for profile source normalizers (SDD §5.3)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseProfileInput(ABC):
    """Contract for converting a supported profile source into plain text."""

    name: str = "unnamed"
    accepts: tuple[str, ...] = ("text",)

    @abstractmethod
    async def to_text(self, source: object) -> str:
        """Return plain profile text from raw text or a future file-like source."""
        raise NotImplementedError
