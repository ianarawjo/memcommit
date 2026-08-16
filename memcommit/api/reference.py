"""Stable public result value for immutable Memory Reference snapshots."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryReferenceResult:
    """Receipt for one exact Source Memory snapshot retained in a Target."""

    reference_uid: str
    source_name: str
    source_uid: str
    memory_uid: str
    memory_content_sha256: str
    into_name: str
    into_uid: str
    checkpoint_uid: str


__all__ = ["MemoryReferenceResult"]
