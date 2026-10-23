"""Shared transfer values and their operation-independent invariants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MemoryTransferKind = Literal["COPY", "MOVE"]


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
            raise ValueError("Copy/Move placement must be nonnegative.")
        if self.position == 0 and self.previous_uid is not None:
            raise ValueError("The first Copy/Move gap has no previous item.")


@dataclass(frozen=True, slots=True)
class FrozenTransferMemory:
    """One exact Source Memory and its direct owner binding."""

    source_context_name: str
    source_context_uid: str
    source_memory_uid: str
    content: str
    output_memory_uid: str


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


def validate_transfer_request_fields(
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
            "Copy/Move requires one or more nonempty Memory locators."
        )
    for value, label in (
        (into_locator, "Target Context"),
        (source_locator, "Source Context"),
        (before, "before selector"),
        (after, "after selector"),
    ):
        if value is not None and (not isinstance(value, str) or not value):
            raise MemoryTransferError(f"Copy/Move {label} must be nonempty text.")
    if before is not None and after is not None:
        raise MemoryTransferError("Pass only one of --before or --after.")


def validate_transfer_plan_fields(
    memories: tuple[FrozenTransferMemory, ...],
    *,
    into_name: str,
    into_uid: str,
    placement: MemoryTransferPlacement,
    plan_digest: str,
) -> None:
    if not memories or len(
        {(item.source_context_uid, item.source_memory_uid) for item in memories}
    ) != len(memories):
        raise MemoryTransferError("Copy/Move plan has duplicate Sources.")
    if not all((into_name, into_uid, plan_digest)):
        raise MemoryTransferError("Copy/Move plan has an incomplete binding.")
    if not isinstance(placement, MemoryTransferPlacement):
        raise TypeError("Copy/Move plan has an invalid placement.")


def transfer_item_results(
    memories: tuple[FrozenTransferMemory, ...],
) -> tuple[MemoryTransferItemResult, ...]:
    return tuple(
        MemoryTransferItemResult(
            source_context_name=item.source_context_name,
            source_context_uid=item.source_context_uid,
            source_memory_uid=item.source_memory_uid,
            into_memory_uid=item.output_memory_uid,
        )
        for item in memories
    )
