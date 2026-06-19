"""Pure batching helpers for AI scoring calls (SDD §5.1 step 9)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def batch_items(items: Sequence[T], *, batch_size: int) -> list[list[T]]:
    """Split ``items`` into order-preserving batches of ``batch_size``."""
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    return [list(items[index : index + batch_size]) for index in range(0, len(items), batch_size)]
