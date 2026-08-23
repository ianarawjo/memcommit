"""Terminal-independent contracts for direct-Memory Copy and Move."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


MemoryTransferKind = Literal["COPY", "MOVE"]
CopyUidPolicy = Literal["FRESH", "PRESERVE"]
MoveLinkPolicy = Literal["BLOCK", "RETARGET", "BREAK"]


class MemoryTransferError(RuntimeError):
    """Raised when one exact Copy or Move cannot be completed atomically."""


class MemoryTransferStalePlanError(MemoryTransferError):
    """Raised when frozen Source, Target, or link evidence changed before Apply."""


@dataclass(frozen=True, slots=True)
class MemoryTransferPlacement:
    """One exact gap in a frozen Target direct-item order."""

    position: int
    previous_uid: str | None
    next_uid: str | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
        ):
            raise ValueError("Memory transfer placement must be nonnegative.")
        if self.position == 0 and self.previous_uid is not None:
            raise ValueError("The first Memory transfer gap has no previous item.")


@dataclass(frozen=True, slots=True)
class CopyMemoriesRequest:
    """Copy directly owned local Memories into one existing local Context."""

    memory_locators: tuple[str, ...]
    into_locator: str | None = None
    source_locator: str | None = None
    before: str | None = None
    after: str | None = None
    uid_policy: CopyUidPolicy = "FRESH"


@dataclass(frozen=True, slots=True)
class MoveMemoriesRequest:
    """Move directly owned local Memories into one existing local Context."""

    memory_locators: tuple[str, ...]
    into_locator: str | None = None
    source_locator: str | None = None
    before: str | None = None
    after: str | None = None
    link_policy: MoveLinkPolicy = "BLOCK"


@dataclass(frozen=True, slots=True)
class FrozenTransferMemory:
    """One exact Source Memory and its direct owner binding."""

    source_context_name: str
    source_context_uid: str
    source_context_digest: str
    source_memory_uid: str
    content: str
    output_memory_uid: str


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
class FrozenCopyMemoriesPlan:
    request: CopyMemoriesRequest
    memories: tuple[FrozenTransferMemory, ...]
    into_name: str
    into_uid: str
    into_digest: str
    placement: MemoryTransferPlacement
    plan_digest: str
    token: object = field(repr=False, compare=False)


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
class MemoryTransferItemResult:
    source_context_name: str
    source_context_uid: str
    source_memory_uid: str
    into_memory_uid: str


@dataclass(frozen=True, slots=True)
class MemoryTransferCheckpoint:
    context_name: str
    context_uid: str
    checkpoint_uid: str


@dataclass(frozen=True, slots=True)
class CopyMemoriesResult:
    into_name: str
    into_uid: str
    uid_policy: CopyUidPolicy
    placement: MemoryTransferPlacement
    items: tuple[MemoryTransferItemResult, ...]
    plan_digest: str
    checkpoints: tuple[MemoryTransferCheckpoint, ...]

    @property
    def count(self) -> int:
        return len(self.items)


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


class MemoryTransferPort(Protocol):
    def freeze_copy(self, request: CopyMemoriesRequest) -> FrozenCopyMemoriesPlan: ...

    def apply_copy(self, plan: FrozenCopyMemoriesPlan) -> CopyMemoriesResult: ...

    def freeze_move(self, request: MoveMemoriesRequest) -> FrozenMoveMemoriesPlan: ...

    def apply_move(self, plan: FrozenMoveMemoriesPlan) -> MoveMemoriesResult: ...


def _validate_common_request(
    memory_locators: tuple[str, ...],
    *,
    into_locator: str | None,
    source_locator: str | None,
    before: str | None,
    after: str | None,
) -> None:
    if (
        not isinstance(memory_locators, tuple)
        or not memory_locators
        or any(not isinstance(value, str) or not value for value in memory_locators)
    ):
        raise MemoryTransferError(
            "Memory transfer requires one or more nonempty Memory locators."
        )
    for value, label in (
        (into_locator, "Target Context"),
        (source_locator, "Source Context"),
        (before, "before selector"),
        (after, "after selector"),
    ):
        if value is not None and (not isinstance(value, str) or not value):
            raise MemoryTransferError(f"Memory transfer {label} must be nonempty text.")
    if before is not None and after is not None:
        raise MemoryTransferError("Pass only one of --before or --after.")


def validate_copy_request(request: CopyMemoriesRequest) -> CopyMemoriesRequest:
    if not isinstance(request, CopyMemoriesRequest):
        raise TypeError("Copy requires a CopyMemoriesRequest.")
    _validate_common_request(
        request.memory_locators,
        into_locator=request.into_locator,
        source_locator=request.source_locator,
        before=request.before,
        after=request.after,
    )
    if request.uid_policy not in {"FRESH", "PRESERVE"}:
        raise MemoryTransferError("Copy uid_policy must be FRESH or PRESERVE.")
    return request


def validate_move_request(request: MoveMemoriesRequest) -> MoveMemoriesRequest:
    if not isinstance(request, MoveMemoriesRequest):
        raise TypeError("Move requires a MoveMemoriesRequest.")
    _validate_common_request(
        request.memory_locators,
        into_locator=request.into_locator,
        source_locator=request.source_locator,
        before=request.before,
        after=request.after,
    )
    if request.link_policy not in {"BLOCK", "RETARGET", "BREAK"}:
        raise MemoryTransferError(
            "Move link_policy must be BLOCK, RETARGET, or BREAK."
        )
    return request


def _validate_plan_common(
    memories: tuple[FrozenTransferMemory, ...],
    *,
    into_name: str,
    into_uid: str,
    into_digest: str,
    placement: MemoryTransferPlacement,
    plan_digest: str,
) -> None:
    if not memories or len({
        (item.source_context_uid, item.source_memory_uid) for item in memories
    }) != len(memories):
        raise MemoryTransferError("Memory transfer plan has duplicate Sources.")
    if not all((into_name, into_uid, into_digest, plan_digest)):
        raise MemoryTransferError("Memory transfer plan has an incomplete binding.")
    if not isinstance(placement, MemoryTransferPlacement):
        raise TypeError("Memory transfer plan has an invalid placement.")


def prepare_copy(
    request: CopyMemoriesRequest,
    *,
    port: MemoryTransferPort,
) -> FrozenCopyMemoriesPlan:
    request = validate_copy_request(request)
    plan = port.freeze_copy(request)
    if not isinstance(plan, FrozenCopyMemoriesPlan):
        raise TypeError("Copy port returned an invalid frozen plan.")
    if plan.request != request:
        raise MemoryTransferError("Copy plan does not describe the request.")
    _validate_plan_common(
        plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
        placement=plan.placement,
        plan_digest=plan.plan_digest,
    )
    if len({item.output_memory_uid for item in plan.memories}) != len(plan.memories):
        raise MemoryTransferError("Copy plan has duplicate output Memory UIDs.")
    return plan


def prepare_move(
    request: MoveMemoriesRequest,
    *,
    port: MemoryTransferPort,
) -> FrozenMoveMemoriesPlan:
    request = validate_move_request(request)
    plan = port.freeze_move(request)
    if not isinstance(plan, FrozenMoveMemoriesPlan):
        raise TypeError("Move port returned an invalid frozen plan.")
    if plan.request != request:
        raise MemoryTransferError("Move plan does not describe the request.")
    _validate_plan_common(
        plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
        placement=plan.placement,
        plan_digest=plan.plan_digest,
    )
    if any(item.output_memory_uid != item.source_memory_uid for item in plan.memories):
        raise MemoryTransferError("Move must preserve every selected Memory UID.")
    if len({item.output_memory_uid for item in plan.memories}) != len(plan.memories):
        raise MemoryTransferError(
            "Move cannot place same-UID branch copies in one Target Context."
        )
    return plan


def run_copy(
    request: CopyMemoriesRequest,
    *,
    port: MemoryTransferPort,
    frozen_plan: FrozenCopyMemoriesPlan | None = None,
) -> CopyMemoriesResult:
    request = validate_copy_request(request)
    plan = frozen_plan or prepare_copy(request, port=port)
    if not isinstance(plan, FrozenCopyMemoriesPlan) or plan.request != request:
        raise MemoryTransferError("Frozen Copy plan no longer matches the request.")
    _validate_plan_common(
        plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
        placement=plan.placement,
        plan_digest=plan.plan_digest,
    )
    if len({item.output_memory_uid for item in plan.memories}) != len(plan.memories):
        raise MemoryTransferError("Copy plan has duplicate output Memory UIDs.")
    result = port.apply_copy(plan)
    if not isinstance(result, CopyMemoriesResult):
        raise TypeError("Copy port returned an invalid durable receipt.")
    expected = tuple(
        MemoryTransferItemResult(
            source_context_name=item.source_context_name,
            source_context_uid=item.source_context_uid,
            source_memory_uid=item.source_memory_uid,
            into_memory_uid=item.output_memory_uid,
        )
        for item in plan.memories
    )
    if (
        result.into_name != plan.into_name
        or result.into_uid != plan.into_uid
        or result.uid_policy != request.uid_policy
        or result.placement != plan.placement
        or result.items != expected
        or result.plan_digest != plan.plan_digest
        or not result.checkpoints
    ):
        raise MemoryTransferError("Copy receipt does not match the frozen plan.")
    return result


def run_move(
    request: MoveMemoriesRequest,
    *,
    port: MemoryTransferPort,
    frozen_plan: FrozenMoveMemoriesPlan | None = None,
) -> MoveMemoriesResult:
    request = validate_move_request(request)
    plan = frozen_plan or prepare_move(request, port=port)
    if not isinstance(plan, FrozenMoveMemoriesPlan) or plan.request != request:
        raise MemoryTransferError("Frozen Move plan no longer matches the request.")
    _validate_plan_common(
        plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
        placement=plan.placement,
        plan_digest=plan.plan_digest,
    )
    if any(item.output_memory_uid != item.source_memory_uid for item in plan.memories):
        raise MemoryTransferError("Move must preserve every selected Memory UID.")
    if len({item.output_memory_uid for item in plan.memories}) != len(plan.memories):
        raise MemoryTransferError(
            "Move cannot place same-UID branch copies in one Target Context."
        )
    result = port.apply_move(plan)
    if not isinstance(result, MoveMemoriesResult):
        raise TypeError("Move port returned an invalid durable receipt.")
    expected = tuple(
        MemoryTransferItemResult(
            source_context_name=item.source_context_name,
            source_context_uid=item.source_context_uid,
            source_memory_uid=item.source_memory_uid,
            into_memory_uid=item.output_memory_uid,
        )
        for item in plan.memories
    )
    inbound_count = len(plan.inbound_links)
    expected_retargeted = inbound_count if request.link_policy == "RETARGET" else 0
    expected_dangling = inbound_count if request.link_policy == "BREAK" else 0
    if (
        result.into_name != plan.into_name
        or result.into_uid != plan.into_uid
        or result.link_policy != request.link_policy
        or result.placement != plan.placement
        or result.items != expected
        or result.inbound_link_count != inbound_count
        or result.retargeted_link_count != expected_retargeted
        or result.dangling_link_count != expected_dangling
        or result.plan_digest != plan.plan_digest
        or not result.checkpoints
    ):
        raise MemoryTransferError("Move receipt does not match the frozen plan.")
    return result


__all__ = [
    "CopyMemoriesRequest",
    "CopyMemoriesResult",
    "CopyUidPolicy",
    "FrozenCopyMemoriesPlan",
    "FrozenInboundMemoryLink",
    "FrozenMoveMemoriesPlan",
    "FrozenTransferMemory",
    "MemoryTransferCheckpoint",
    "MemoryTransferError",
    "MemoryTransferItemResult",
    "MemoryTransferKind",
    "MemoryTransferPlacement",
    "MemoryTransferPort",
    "MemoryTransferStalePlanError",
    "MoveLinkPolicy",
    "MoveMemoriesRequest",
    "MoveMemoriesResult",
    "prepare_copy",
    "prepare_move",
    "run_copy",
    "run_move",
    "validate_copy_request",
    "validate_move_request",
]
