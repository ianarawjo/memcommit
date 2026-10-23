"""Move request, frozen plan, and durable result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferCheckpoint,
    MemoryTransferItemResult,
    MemoryTransferPlacement,
)


@dataclass(frozen=True, slots=True)
class MoveMemoriesRequest:
    """Move directly owned local Memories into one existing local Context."""

    memory_locators: tuple[str, ...]
    into_locator: str | None = None
    source_locator: str | None = None
    before: str | None = None
    after: str | None = None


@dataclass(frozen=True, slots=True)
class FrozenMoveMemoriesPlan:
    request: MoveMemoriesRequest
    memories: tuple[FrozenTransferMemory, ...]
    into_name: str
    into_uid: str
    placement: MemoryTransferPlacement
    plan_digest: str
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class MoveMemoriesResult:
    into_name: str
    into_uid: str
    placement: MemoryTransferPlacement
    items: tuple[MemoryTransferItemResult, ...]
    plan_digest: str
    checkpoints: tuple[MemoryTransferCheckpoint, ...]

    @property
    def count(self) -> int:
        return len(self.items)
