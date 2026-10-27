"""Captured Context frames, explicit access snapshots, and runtime ownership checks."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferError,
)
from memcommit.application.context_access.access import (
    ContextAccess,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.persistence.store import ProfileStore


@dataclass(frozen=True, slots=True)
class StoreTransferFrame:
    context: Context
    display_name: str
    access: ContextAccess


@dataclass(frozen=True, slots=True)
class StoreTransferToken:
    owner: object
    operation_uid: str
    plan_digest: str
    frames: tuple[StoreTransferFrame, ...]
    context_catalog: tuple[str, ...]


def capture_context_frames(store: ProfileStore) -> tuple[StoreTransferFrame, ...]:
    contexts = store.load_all_contexts()
    return tuple(
        StoreTransferFrame(
            context=context,
            display_name=context.name,
            access=ContextAccess(
                store=store,
                context_name=context.name,
                access_name=context.name,
            ),
        )
        for context in contexts
    )


def validate_context_bindings(
    token: object,
    *,
    owner: object,
    plan_digest: str,
    expected_plan_digest: str,
    memories: tuple[FrozenTransferMemory, ...],
    into_name: str,
    into_uid: str,
) -> StoreTransferToken:
    """Keep runtime identity and exact frozen data bound independently of effect policy."""
    if not isinstance(token, StoreTransferToken) or token.owner is not owner:
        raise MemoryTransferError("Copy/Move plan belongs to a different runtime.")
    if plan_digest != token.plan_digest or expected_plan_digest != plan_digest:
        raise MemoryTransferError("Copy/Move frozen plan was modified.")
    frames = {frame.display_name: frame for frame in token.frames}
    try:
        into = frames[into_name]
    except KeyError as error:
        raise MemoryTransferError("Copy/Move lost its Target binding.") from error
    if into.context.uid != into_uid:
        raise MemoryTransferError("Copy/Move Target binding changed.")
    for item in memories:
        frame = frames.get(item.source_context_name)
        if (
            frame is None or frame.context.uid != item.source_context_uid
        ):
            raise MemoryTransferError("Copy/Move Source binding changed.")
        memory = frame.context.memories.get(item.source_memory_uid)
        if not isinstance(memory, Memory) or memory.content != item.content:
            raise MemoryTransferError("Copy/Move opaque Source changed.")
    return token
