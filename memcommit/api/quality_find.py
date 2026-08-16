"""Stable public values for read-only quality finding operations."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.quality_finding_handoff import QualityFindingHandoff


@dataclass(frozen=True)
class QualityFindResult:
    """One complete finder result with adapter-neutral next-operation receipts."""

    kind: str
    context_names: tuple[str, ...]
    source_digest: str
    memory_count: int
    pair_count: int | None
    handoffs: tuple[QualityFindingHandoff, ...]


__all__ = ["QualityFindResult"]
