"""Stable public values for the unified Delete operation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DeletedItemKind = Literal[
    "MEMORY",
    "MEMORY_REF",
    "QUERY_CONTEXT_REF",
    "CONTEXT",
]
ContextDeleteStatus = Literal["APPLIED", "APPLIED_WITH_CLEANUP_WARNING"]


@dataclass(frozen=True, slots=True)
class DeletedDirectItemResult:
    kind: DeletedItemKind
    uid: str
    content: str | None
    name: str | None
    target_context_name: str | None
    target_memory_uid: str | None


@dataclass(frozen=True, slots=True)
class DirectItemDeleteReceipt:
    context_name: str
    context_uid: str
    item: DeletedDirectItemResult
    checkpoint_uid: str
    undoable: bool = True


@dataclass(frozen=True, slots=True)
class ContextDeletePlanResult:
    context_name: str
    context_uid: str
    context_digest: str
    plan_digest: str
    descendants_preserved: bool
    checkpoint_history_deleted: bool
    restorable_snapshot_retained: bool
    lifecycle_metadata_retained: bool
    _handle: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ContextDeleteReceipt:
    status: ContextDeleteStatus
    context_name: str
    context_uid: str
    context_digest: str
    plan_digest: str
    event_uid: str
    operation_id: str
    previous_checkpoint_status: str
    descendants_preserved: bool
    cleanup_warning: str | None
    undoable: bool = False


__all__ = [
    "ContextDeletePlanResult",
    "ContextDeleteReceipt",
    "ContextDeleteStatus",
    "DeletedDirectItemResult",
    "DeletedItemKind",
    "DirectItemDeleteReceipt",
]
