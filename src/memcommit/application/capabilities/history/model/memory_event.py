"""Immutable Memory event vocabulary shared by History consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..verification.model import (
    MemoryHistoryChildEvidence,
    MemoryHistoryCommandOperation,
    MemoryHistoryContextTransition,
    MemoryHistoryEvidence,
    MemoryState,
    SourceOccurrence,
)

MemoryHistoryEventKind = Literal[
    "CREATED",
    "EDITED",
    "REMOVED",
    "SPLIT",
    "ABSORBED",
    "MERGED_IN",
    "RESTORED",
    "TRANSLATED",
    "ATOMIZE_KEEP",
    "ATOMIZE_PRESERVED",
    "MELDED",
    "BRANCHED",
    "REORDERED",
    "HISTORY_GAP",
]


@dataclass(frozen=True)
class MemoryHistoryEvent:
    kind: MemoryHistoryEventKind
    evidence: MemoryHistoryEvidence
    timestamp: str | None
    checkpoint_uid: str | None
    command: str
    description: str
    before: tuple[MemoryState, ...] = ()
    after: tuple[MemoryState, ...] = ()
    reason: str | None = None
    reason_codes: tuple[str, ...] = ()
    source_occurrence: SourceOccurrence | None = None
    operation_id: str | None = None
    command_operation: MemoryHistoryCommandOperation | None = None
    context_transition: MemoryHistoryContextTransition | None = None
    child_evidence: tuple[MemoryHistoryChildEvidence, ...] = ()
    declared_frame: str | None = None
    declared_frame_digest: str | None = None
    uncertainty_reason: str | None = None
    source_review_uid: str | None = None
    source_review_digest: str | None = None
    source_analysis_uid: str | None = None

    @property
    def uids(self) -> set[str]:
        return {state.uid for state in (*self.before, *self.after)}

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "checkpoint_uid": self.checkpoint_uid,
            "command": self.command,
            "description": self.description,
            "before": [state.to_dict() for state in self.before],
            "after": [state.to_dict() for state in self.after],
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "source_occurrence": (
                self.source_occurrence.to_dict()
                if self.source_occurrence is not None
                else None
            ),
            "operation_id": self.operation_id,
            "command_operation": (
                self.command_operation.to_dict()
                if self.command_operation is not None
                else None
            ),
            "context_transition": (
                self.context_transition.to_dict()
                if self.context_transition is not None
                else None
            ),
            "child_evidence": [evidence.to_dict() for evidence in self.child_evidence],
            "declared_frame": self.declared_frame,
            "declared_frame_digest": self.declared_frame_digest,
            "uncertainty_reason": self.uncertainty_reason,
            "source_review_uid": self.source_review_uid,
            "source_review_digest": self.source_review_digest,
            "source_analysis_uid": self.source_analysis_uid,
        }
