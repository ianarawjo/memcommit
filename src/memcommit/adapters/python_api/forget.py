"""Stable public values for process-local Forget review and Apply."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.application.operations.forget.application import ForgetSessionSnapshot


@dataclass(frozen=True)
class ForgetCandidateResult:
    uid: str
    source_memory_uid: str
    source_content: str
    recommendation: str
    proposed_content: str
    rationale: str
    selection: str
    selected_action: str
    selected_content: str


@dataclass(frozen=True)
class ForgetReviewResult:
    review_uid: str
    version: str
    source_context: str
    source_context_uid: str
    instruction: str
    overview: str
    candidates: tuple[ForgetCandidateResult, ...]
    provider_used: bool
    _snapshot: ForgetSessionSnapshot = field(repr=False, compare=False)
    _store_root: Path = field(repr=False, compare=False)
    retention: str = "PROCESS_LOCAL"


@dataclass(frozen=True)
class ForgetApplyResult:
    review_uid: str
    version: str
    source_context: str
    source_context_uid: str
    removed_count: int
    edited_count: int
    checkpoint_uid: str | None
    undo_available: bool
    granted: bool
    applied: bool

    @property
    def changed_count(self) -> int:
        return self.removed_count + self.edited_count


__all__ = [
    "ForgetApplyResult",
    "ForgetCandidateResult",
    "ForgetReviewResult",
]
