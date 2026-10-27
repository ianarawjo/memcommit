"""Freeze Copy's exact Sources, placement, and operation-specific effects."""

from __future__ import annotations

import uuid

from memcommit.application.capabilities.memory_transfer.context_bindings import (
    StoreTransferToken,
    capture_context_frames,
)
from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
)
from memcommit.application.capabilities.memory_transfer.locators import (
    placement_for_context,
    resolve_source_memories,
    target_frame,
)
from memcommit.application.capabilities.memory_transfer.plan_digest import (
    transfer_plan_digest,
)
from memcommit.application.operations.copy.application import validate_copy_request
from memcommit.application.operations.copy.contracts import (
    CopyMemoriesRequest,
    FrozenCopyMemoriesPlan,
)
from memcommit.persistence.store import ProfileStore


def freeze_copy(
    request: CopyMemoriesRequest,
    *,
    store: ProfileStore,
    current_name: str | None,
    owner: object,
) -> FrozenCopyMemoriesPlan:
    request = validate_copy_request(request)
    local_frames = capture_context_frames(store)
    frames = local_frames
    into = target_frame(
        local_frames,
        request.into_locator,
        current_name=current_name,
    )
    # Copy is deliberately not a branching primitive. Every output gets a
    # store-wide fresh identity so two independently editable Memories can
    # never imply synchronization merely because they share a UID.
    occupied = {uid for frame in local_frames for uid in frame.context.memories}
    generated: list[str] = []
    while len(generated) < len(request.memory_locators):
        candidate = str(uuid.uuid4())
        if candidate not in occupied and candidate not in generated:
            generated.append(candidate)
    output_uids = tuple(generated)
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
            output_memory_uid=output_uid,
        )
        for (frame, memory), output_uid in zip(sources, output_uids, strict=True)
    )
    placement = placement_for_context(
        into.context,
        before=request.before,
        after=request.after,
    )
    digest = transfer_plan_digest(
        kind="COPY",
        memories=memories,
        into_name=into.context.name,
        into_uid=into.context.uid,
        placement=placement,
        policy="NEW_UIDS",
    )
    return FrozenCopyMemoriesPlan(
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


def copy_plan_digest(plan: FrozenCopyMemoriesPlan) -> str:
    return transfer_plan_digest(
        kind="COPY",
        memories=plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        placement=plan.placement,
        policy="NEW_UIDS",
    )
