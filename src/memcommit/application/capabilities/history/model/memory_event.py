"""Command changes and their independently recorded Memory lineage relations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias, get_args

from ..verification.model import (
    MemoryHistoryChildEvidence,
    MemoryHistoryCommandOperation,
    MemoryHistoryContextTransition,
    MemoryState,
    SourceOccurrence,
)

MemoryHistoryEventKind = Literal["ADD", "EDIT", "REMOVE", "REORDER"]
MemoryHistoryRelationKind = Literal["DERIVED_FROM", "CONTINUES_AS"]


@dataclass(frozen=True)
class MemoryHistorySource:
    context_uid: str
    context_name: str
    memory_uid: str
    content_digest: str

    def to_dict(self) -> dict[str, str]:
        return dict(self.__dict__)


@dataclass(frozen=True, kw_only=True)
class _MemoryHistoryRecord:
    timestamp: str | None
    checkpoint_uid: str | None
    command: str
    description: str
    before: tuple[MemoryState, ...] = ()
    after: tuple[MemoryState, ...] = ()
    reason: str | None = None
    reason_codes: tuple[str, ...] = ()
    sources: tuple[MemoryHistorySource, ...] = ()
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
            "timestamp": self.timestamp,
            "checkpoint_uid": self.checkpoint_uid,
            "command": self.command,
            "description": self.description,
            "before": [state.to_dict() for state in self.before],
            "after": [state.to_dict() for state in self.after],
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "sources": [source.to_dict() for source in self.sources],
            "source_occurrence": self.source_occurrence.to_dict()
            if self.source_occurrence
            else None,
            "operation_id": self.operation_id,
            "command_operation": self.command_operation.to_dict()
            if self.command_operation
            else None,
            "context_transition": self.context_transition.to_dict()
            if self.context_transition
            else None,
            "child_evidence": [child.to_dict() for child in self.child_evidence],
            "declared_frame": self.declared_frame,
            "declared_frame_digest": self.declared_frame_digest,
            "uncertainty_reason": self.uncertainty_reason,
            "source_review_uid": self.source_review_uid,
            "source_review_digest": self.source_review_digest,
            "source_analysis_uid": self.source_analysis_uid,
        }


@dataclass(frozen=True, kw_only=True)
class MemoryHistoryEvent(_MemoryHistoryRecord):
    """One physical change; operation names never become change kinds."""

    kind: MemoryHistoryEventKind

    def __post_init__(self) -> None:
        if self.kind not in get_args(MemoryHistoryEventKind):
            raise ValueError(
                "Memory History changes must be ADD, EDIT, REMOVE or REORDER."
            )


@dataclass(frozen=True, kw_only=True)
class MemoryHistoryRelation(_MemoryHistoryRecord):
    """Recorded source/result connectivity, including unchanged results."""

    kind: MemoryHistoryRelationKind = "DERIVED_FROM"

    def __post_init__(self) -> None:
        if self.kind not in get_args(MemoryHistoryRelationKind):
            raise ValueError("Invalid Memory operation relation.")


MemoryHistoryRecord: TypeAlias = MemoryHistoryEvent | MemoryHistoryRelation
