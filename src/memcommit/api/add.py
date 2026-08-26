"""Stable public result values for Add."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AddedMemoryResult:
    """One exact Memory created by a completed public Add call."""

    uid: str
    content: str


@dataclass(frozen=True)
class AddMemoriesResult:
    """Receipt for one ordered batch and its single durable checkpoint."""

    context_name: str
    context_uid: str
    memories: tuple[AddedMemoryResult, ...]
    checkpoint_uid: str

    @property
    def count(self) -> int:
        return len(self.memories)


__all__ = ["AddMemoriesResult", "AddedMemoryResult"]
