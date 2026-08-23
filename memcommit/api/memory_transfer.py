"""Stable public values for direct-Memory Copy and Move."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CopyUidPolicyResult = Literal["FRESH", "PRESERVE"]
MoveLinkPolicyResult = Literal["BLOCK", "RETARGET", "BREAK"]


@dataclass(frozen=True, slots=True)
class MemoryTransferPlacementResult:
    position: int
    previous_uid: str | None
    next_uid: str | None


@dataclass(frozen=True, slots=True)
class MemoryTransferItemResult:
    source_context_name: str
    source_context_uid: str
    source_memory_uid: str
    into_memory_uid: str


@dataclass(frozen=True, slots=True)
class MemoryTransferCheckpointResult:
    context_name: str
    context_uid: str
    checkpoint_uid: str


@dataclass(frozen=True, slots=True)
class CopyMemoriesReceipt:
    into_context_name: str
    into_context_uid: str
    uid_policy: CopyUidPolicyResult
    placement: MemoryTransferPlacementResult
    items: tuple[MemoryTransferItemResult, ...]
    plan_digest: str
    checkpoints: tuple[MemoryTransferCheckpointResult, ...]
    undoable: bool = True

    @property
    def count(self) -> int:
        return len(self.items)


@dataclass(frozen=True, slots=True)
class MoveMemoriesReceipt:
    into_context_name: str
    into_context_uid: str
    link_policy: MoveLinkPolicyResult
    placement: MemoryTransferPlacementResult
    items: tuple[MemoryTransferItemResult, ...]
    inbound_link_count: int
    retargeted_link_count: int
    dangling_link_count: int
    plan_digest: str
    checkpoints: tuple[MemoryTransferCheckpointResult, ...]
    undoable: bool = True

    @property
    def count(self) -> int:
        return len(self.items)


__all__ = [
    "CopyMemoriesReceipt",
    "CopyUidPolicyResult",
    "MemoryTransferCheckpointResult",
    "MemoryTransferItemResult",
    "MemoryTransferPlacementResult",
    "MoveLinkPolicyResult",
    "MoveMemoriesReceipt",
]
