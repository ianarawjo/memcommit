"""Stable public result values for live Context and Memory Embed links."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbedPlacementResult:
    """The exact direct-item gap used by one completed Embed."""

    position: int
    previous_uid: str | None
    next_uid: str | None


@dataclass(frozen=True)
class EmbeddedContextResult:
    """Receipt for one live Context Embed."""

    child_name: str
    child_uid: str
    into_name: str
    into_uid: str
    placement: EmbedPlacementResult
    checkpoint_uid: str


@dataclass(frozen=True)
class EmbeddedMemoryResult:
    """Receipt for one live Source Memory Embed."""

    embed_uid: str
    source_name: str
    source_uid: str
    memory_uid: str
    into_name: str
    into_uid: str
    placement: EmbedPlacementResult
    checkpoint_uid: str


__all__ = [
    "EmbeddedContextResult",
    "EmbeddedMemoryResult",
    "EmbedPlacementResult",
]
