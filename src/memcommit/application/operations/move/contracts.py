"""Move request, frozen plan, and durable result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferCheckpoint,
    MemoryTransferItemResult,
    MemoryTransferPlacement,
)

MoveLinkPolicy = Literal["BLOCK", "RETARGET", "BREAK"]


@dataclass(frozen=True, slots=True)
class MoveMemoriesRequest:
    """Move directly owned local Memories into one existing local Context."""

    memory_locators: tuple[str, ...]
    into_locator: str | None = None
    source_locator: str | None = None
    before: str | None = None
    after: str | None = None
    # A live Embed names the Memory's current owner binding, so moving that
    # Memory retargets the local live link atomically unless breakage is an
    # explicit request. Immutable Reference snapshots never participate.
    link_policy: MoveLinkPolicy = "RETARGET"


@dataclass(frozen=True, slots=True)
class FrozenInboundMemoryLink:
    """One direct live Embed that targets a Memory selected for Move."""

    owner_context_name: str
    owner_context_uid: str
    owner_context_digest: str
    reference_uid: str
    source_context_uid: str
    source_memory_uid: str


@dataclass(frozen=True, slots=True)
class FrozenMoveMemoriesPlan:
    request: MoveMemoriesRequest
    memories: tuple[FrozenTransferMemory, ...]
    into_name: str
    into_uid: str
    into_digest: str
    placement: MemoryTransferPlacement
    inbound_links: tuple[FrozenInboundMemoryLink, ...]
    plan_digest: str
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class MoveMemoriesResult:
    into_name: str
    into_uid: str
    link_policy: MoveLinkPolicy
    placement: MemoryTransferPlacement
    items: tuple[MemoryTransferItemResult, ...]
    inbound_link_count: int
    retargeted_link_count: int
    dangling_link_count: int
    plan_digest: str
    checkpoints: tuple[MemoryTransferCheckpoint, ...]

    @property
    def count(self) -> int:
        return len(self.items)
