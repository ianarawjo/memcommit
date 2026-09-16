"""Freeze Move's exact Sources, placement, and operation-specific effects."""

from __future__ import annotations

import uuid

from memcommit.application.capabilities.memory_transfer.context_bindings import (
    StoreTransferToken,
    capture_context_frames,
    source_access_snapshot,
)
from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferAuthorityError,
    MemoryTransferError,
)
from memcommit.application.capabilities.memory_transfer.locators import (
    placement_for_context,
    resolve_source_memories,
    source_owner_locators,
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
from memcommit.application.operations.move.runtime.live_embeds import (
    find_inbound_links,
    inbound_link_digest_values,
    validate_live_embed_policy,
)
from memcommit.persistence.store import MemoryStore


def freeze_move(
    request: MoveMemoriesRequest,
    *,
    store: MemoryStore,
    current_name: str | None,
    owner: object,
    allow_granted_sources: bool,
) -> FrozenMoveMemoriesPlan:
    request = validate_move_request(request)
    local_frames = capture_context_frames(store)
    # Recognize a granted public Source for a precise rejection, without opening it.
    with source_access_snapshot(
        store,
        source_owner_locators(request.memory_locators, request.source_locator),
        current_name=current_name,
        inspect_grants=allow_granted_sources,
    ) as accesses:
        for access in accesses:
            if access.is_granted:
                raise MemoryTransferAuthorityError(
                    f"Move cannot use granted Source {access.access_name!r}: READ "
                    "permits a Copy, not deletion or cross-Profile ownership "
                    "transfer. Copy it into a local Context first, then move "
                    "the local copy."
                )
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
            source_context_digest=frame.expected_digest,
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
    inbound_links = find_inbound_links(memories, frames)
    validate_live_embed_policy(
        inbound_links,
        policy=request.link_policy,
        into_uid=into.context.uid,
    )
    digest = transfer_plan_digest(
        kind="MOVE",
        memories=memories,
        into_name=into.context.name,
        into_uid=into.context.uid,
        into_digest=into.expected_digest,
        placement=placement,
        policy=request.link_policy,
        inbound_links=inbound_link_digest_values(inbound_links),
    )
    return FrozenMoveMemoriesPlan(
        request=request,
        memories=memories,
        into_name=into.context.name,
        into_uid=into.context.uid,
        into_digest=into.expected_digest,
        placement=placement,
        inbound_links=inbound_links,
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
        into_digest=plan.into_digest,
        placement=plan.placement,
        policy=plan.request.link_policy,
        inbound_links=inbound_link_digest_values(plan.inbound_links),
    )
