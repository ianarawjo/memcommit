"""Stable public values for read-only quality finding operations."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    ExactDuplicateGroup,
)
from memcommit.application.capabilities.reviewing.memory_issue.resolution.handoff import (
    QualityFindingHandoff,
)


@dataclass(frozen=True)
class QualityFindContextResult:
    """One independently analyzed direct Context frame."""

    context_name: str
    source_digest: str
    memory_count: int
    handoffs: tuple[QualityFindingHandoff, ...]
    exact_item_groups: tuple[ExactDuplicateGroup, ...] = ()

    @property
    def evidence(self) -> tuple[QualityFindingHandoff, ...]:
        return self.handoffs


@dataclass(frozen=True)
class QualityFindResult:
    """One complete finder result with adapter-neutral evidence."""

    kind: str
    context_names: tuple[str, ...]
    source_digest: str
    memory_count: int
    pair_count: int | None
    handoffs: tuple[QualityFindingHandoff, ...]
    exact_item_groups: tuple[ExactDuplicateGroup, ...] = ()
    include_descendants: bool = False
    contexts: tuple[QualityFindContextResult, ...] = ()

    @property
    def evidence(self) -> tuple[QualityFindingHandoff, ...]:
        """Canonical name for findings that can enter a receiving operation."""

        return self.handoffs


__all__ = ["QualityFindContextResult", "QualityFindResult"]
