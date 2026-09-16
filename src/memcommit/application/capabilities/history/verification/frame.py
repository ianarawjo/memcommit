"""Normalize retained Context snapshots into comparable Memory frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from memcommit.core.context import Context, Memory
from memcommit.persistence.store import (
    canonical_context_record,
    context_record_digest,
)

from .model import MemoryHistoryReconstructionError, MemoryState


@dataclass(frozen=True)
class _Frame:
    context_uid: str
    context_name: str
    memories: dict[str, MemoryState]
    order: tuple[str, ...]
    record: dict[str, Any]
    record_digest: str


def _empty_frame(context_uid: str, context_name: str) -> _Frame:
    record: dict[str, Any] = {
        "uid": context_uid,
        "name": context_name,
        "memories": {},
        "order": [],
    }
    return _Frame(
        context_uid=context_uid,
        context_name=context_name,
        memories={},
        order=(),
        record=record,
        record_digest=context_record_digest(record),
    )


def _frame_from_snapshot(value: object, *, label: str) -> _Frame:
    if not isinstance(value, dict):
        raise MemoryHistoryReconstructionError(
            f"{label} is not a valid Context snapshot."
        )
    context_uid = value.get("uid")
    context_name = value.get("name")
    serialized = value.get("memories")
    if (
        not isinstance(context_uid, str)
        or not context_uid
        or not isinstance(context_name, str)
        or not context_name
        or not isinstance(serialized, dict)
    ):
        raise MemoryHistoryReconstructionError(
            f"{label} is not a valid Context snapshot."
        )

    requested_order = value.get("order")
    ordered_uids: list[str] = []
    seen: set[str] = set()
    if isinstance(requested_order, list):
        for uid in requested_order:
            if isinstance(uid, str) and uid in serialized and uid not in seen:
                ordered_uids.append(uid)
                seen.add(uid)
    for uid in serialized:
        if isinstance(uid, str) and uid not in seen:
            ordered_uids.append(uid)
            seen.add(uid)

    memories: dict[str, MemoryState] = {}
    memory_order: list[str] = []
    for uid in ordered_uids:
        item = serialized.get(uid)
        if not isinstance(item, dict):
            raise MemoryHistoryReconstructionError(
                f"{label} contains an invalid direct item."
            )
        if item.get("type") != "memory":
            continue
        item_uid = item.get("uid")
        content = item.get("content")
        if item_uid != uid or not isinstance(content, str):
            raise MemoryHistoryReconstructionError(
                f"{label} contains an invalid Memory."
            )
        memories[uid] = MemoryState(
            uid=uid,
            content=content,
            position=len(memory_order),
        )
        memory_order.append(uid)

    canonical_record = canonical_context_record(value)
    return _Frame(
        context_uid=context_uid,
        context_name=context_name,
        memories=memories,
        order=tuple(memory_order),
        record=canonical_record,
        record_digest=context_record_digest(canonical_record),
    )


def _frame_from_context(ctx: Context) -> _Frame:
    record = ctx.to_dict()
    memories: dict[str, MemoryState] = {}
    order: list[str] = []
    for item in ctx.iter_items():
        if not isinstance(item, Memory):
            continue
        memories[item.uid] = MemoryState(
            uid=item.uid,
            content=item.content,
            position=len(order),
        )
        order.append(item.uid)
    return _Frame(
        context_uid=ctx.uid,
        context_name=ctx.name,
        memories=memories,
        order=tuple(order),
        record=record,
        record_digest=context_record_digest(record),
    )


def _frame_equal(left: _Frame, right: _Frame) -> bool:
    return left.order == right.order and {
        uid: state.content for uid, state in left.memories.items()
    } == {uid: state.content for uid, state in right.memories.items()}


def _ordered_states(frame: _Frame, uids: Iterable[str]) -> tuple[MemoryState, ...]:
    wanted = set(uids)
    return tuple(frame.memories[uid] for uid in frame.order if uid in wanted)
