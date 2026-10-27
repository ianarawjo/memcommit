"""Freeze Move's exact Sources, placement, and operation-specific effects."""

from __future__ import annotations

import uuid

from memcommit.application.capabilities.memory_transfer.context_bindings import (
    StoreTransferToken,
    capture_context_frames,
)
from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferError,
)
from memcommit.application.capabilities.memory_transfer.locators import (
    placement_for_context,
    resolve_source_memories,
    target_frame,
)
from memcommit.application.capabilities.memory_transfer.plan_digest import (
    transfer_plan_digest,
)
from memcommit.application.operations.move.application import validate_move_request
from memcommit.application.operations.move.contracts import (
    FrozenMoveMemoriesPlan,
    MoveMemoriesRequest,
)
from memcommit.persistence.store import ProfileStore


def freeze_move(
    request: MoveMemoriesRequest,
    *,
    store: ProfileStore,
    current_name: str | None,
    owner: object,
) -> FrozenMoveMemoriesPlan:
    request = validate_move_request(request)
    local_frames = capture_context_frames(store)
    frames = local_frames
    into = target_frame(
        local_frames,
        request.into_locator,
        current_name=current_name,
    )
    sources = resolve_source_memories(
        request.memory_locators,
        source_locator=request.source_locator,
        frames=frames,
        current_name=current_name,
    )
    memories = tuple(
        FrozenTransferMemory(
            source_context_name=frame.display_name,
            source_context_uid=frame.context.uid,
            source_memory_uid=memory.uid,
            content=memory.content,
            output_memory_uid=memory.uid,
        )
        for frame, memory in sources
    )
    same_owner = tuple(
        item for item in memories if item.source_context_uid == into.context.uid
    )
    if same_owner:
        raise MemoryTransferError(
            "Move Target already owns selected Memory/ies: "
            + ", ".join(f"[{item.source_memory_uid[:8]}]" for item in same_owner)
            + ". Use Edit for content or a separate reorder operation."
        )
    collisions = tuple(
        item.source_memory_uid
        for item in memories
        if item.source_memory_uid in into.context.memories
    )
    if collisions:
        raise MemoryTransferError(
            "Move would collide with direct-item UID(s) already present in "
            f"Target '{into.context.name}': "
            + ", ".join(f"[{uid[:8]}]" for uid in collisions)
        )
    placement = placement_for_context(
        into.context,
        before=request.before,
        after=request.after,
    )
    digest = transfer_plan_digest(
        kind="MOVE",
        memories=memories,
        into_name=into.context.name,
        into_uid=into.context.uid,
        placement=placement,
        policy="PRESERVE_UIDS",
    )
    return FrozenMoveMemoriesPlan(
        request=request,
        memories=memories,
        into_name=into.context.name,
        into_uid=into.context.uid,
        placement=placement,
        plan_digest=digest,
        token=StoreTransferToken(
            owner=owner,
            operation_uid=str(uuid.uuid4()),
            plan_digest=digest,
            frames=frames,
            context_catalog=tuple(frame.context.name for frame in local_frames),
        ),
    )


def move_plan_digest(plan: FrozenMoveMemoriesPlan) -> str:
    return transfer_plan_digest(
        kind="MOVE",
        memories=plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        placement=plan.placement,
        policy="PRESERVE_UIDS",
    )
