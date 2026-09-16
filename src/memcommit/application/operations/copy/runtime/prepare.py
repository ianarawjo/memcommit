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
    source_owner_locators,
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
from memcommit.application.operations.copy.runtime.granted_sources import (
    CopyStoreToken,
    copy_authority_checks,
    frozen_transfer_authority,
    load_granted_source_frames,
    unique_source_accesses,
)
from memcommit.persistence.store import MemoryStore


def freeze_copy(
    request: CopyMemoriesRequest,
    *,
    store: MemoryStore,
    current_name: str | None,
    owner: object,
    allow_granted_sources: bool,
) -> FrozenCopyMemoriesPlan:
    request = validate_copy_request(request)
    local_frames = capture_context_frames(store)
    frames = load_granted_source_frames(
        store,
        local_frames,
        owner_locators=source_owner_locators(
            request.memory_locators, request.source_locator
        ),
        current_name=current_name,
        allow_granted_sources=allow_granted_sources,
    )
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
            source_context_digest=frame.expected_digest,
            source_memory_uid=memory.uid,
            content=memory.content,
            output_memory_uid=output_uid,
            source_authority=frozen_transfer_authority(frame.access),
        )
        for (frame, memory), output_uid in zip(sources, output_uids, strict=True)
    )
    frames_by_name = {frame.display_name: frame for frame in frames}
    accesses = unique_source_accesses(memories, frames_by_name)
    authority_checks = copy_authority_checks(accesses)
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
        into_digest=into.expected_digest,
        placement=placement,
        policy="NEW_UIDS",
    )
    return FrozenCopyMemoriesPlan(
        request=request,
        memories=memories,
        into_name=into.context.name,
        into_uid=into.context.uid,
        into_digest=into.expected_digest,
        placement=placement,
        plan_digest=digest,
        token=CopyStoreToken(
            bindings=StoreTransferToken(
                owner=owner,
                operation_uid=str(uuid.uuid4()),
                plan_digest=digest,
                frames=frames,
                context_catalog=tuple(frame.context.name for frame in local_frames),
            ),
            authority_checks=authority_checks,
        ),
    )


def copy_plan_digest(plan: FrozenCopyMemoriesPlan) -> str:
    return transfer_plan_digest(
        kind="COPY",
        memories=plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
        placement=plan.placement,
        policy="NEW_UIDS",
    )
