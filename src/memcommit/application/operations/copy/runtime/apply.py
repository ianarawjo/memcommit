"""Apply one frozen Copy plan through the Store command-batch boundary."""

from __future__ import annotations

from memcommit.application.capabilities.memory_transfer.checkpoint_metadata import (
    transfer_checkpoint_metadata,
)
from memcommit.application.capabilities.memory_transfer.context_bindings import (
    validate_context_bindings,
)
from memcommit.application.capabilities.memory_transfer.contracts import (
    MemoryTransferCheckpoint,
    MemoryTransferError,
    MemoryTransferStalePlanError,
    transfer_item_results,
)
from memcommit.application.capabilities.memory_transfer.locators import (
    unique_local_source_frames,
)
from memcommit.application.operations.copy.contracts import (
    CopyMemoriesResult,
    FrozenCopyMemoriesPlan,
)
from memcommit.application.operations.copy.runtime.granted_sources import (
    CopyStoreToken,
    locked_granted_sources,
)
from memcommit.application.operations.copy.runtime.prepare import copy_plan_digest
from memcommit.core.context import AutoCheckpoint, Memory
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def apply_copy(
    plan: FrozenCopyMemoriesPlan,
    *,
    store: MemoryStore,
    owner: object,
) -> CopyMemoriesResult:
    if not isinstance(plan, FrozenCopyMemoriesPlan):
        raise TypeError("Copy requires its own frozen plan.")
    if not isinstance(plan.token, CopyStoreToken):
        raise MemoryTransferError("Copy/Move plan belongs to a different runtime.")
    bindings = plan.token.bindings
    token = validate_context_bindings(
        bindings,
        owner=owner,
        plan_digest=plan.plan_digest,
        expected_plan_digest=copy_plan_digest(plan),
        memories=plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
    )
    frames = {frame.display_name: frame for frame in token.frames}
    into = frames[plan.into_name]
    for offset, item in enumerate(plan.memories):
        into.context.add(
            Memory(uid=item.output_memory_uid, content=item.content),
            position=plan.placement.position + offset,
        )
    affected = (into,)
    description = (
        f"Copied {len(plan.memories)} Memory/ies into '{plan.into_name}' with new UIDs."
    )
    args = transfer_checkpoint_metadata(
        kind="COPY",
        operation_uid=token.operation_uid,
        plan_digest=plan.plan_digest,
        policy_name="copy_identity",
        policy="NEW_UIDS",
        into_name=into.context.name,
        into_uid=into.context.uid,
        placement=plan.placement,
        memories=plan.memories,
        inbound_links=(),
        affected_contexts=tuple(
            (frame.context.name, frame.context.uid) for frame in affected
        ),
    )
    source_frames = unique_local_source_frames(plan.memories, frames)
    try:
        with locked_granted_sources(
            plan.memories,
            frames,
            authority_checks=plan.token.authority_checks,
        ):
            checkpoints = store.save_context_command_batch(
                (
                    (
                        into.context,
                        AutoCheckpoint(
                            command="copy",
                            args=args,
                            description=description,
                        ),
                        into.expected_digest,
                    ),
                ),
                source_bindings=tuple(
                    (
                        frame.context.name,
                        frame.context.uid,
                        frame.expected_digest,
                    )
                    for frame in source_frames
                ),
            )
    except ConcurrentContextUpdateError as error:
        raise MemoryTransferStalePlanError(
            "Copy Source or Target changed before publication; nothing was copied."
        ) from error
    receipts = (
        MemoryTransferCheckpoint(
            context_name=into.context.name,
            context_uid=into.context.uid,
            checkpoint_uid=checkpoints[0].uid,
        ),
    )
    return CopyMemoriesResult(
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        placement=plan.placement,
        items=transfer_item_results(plan.memories),
        plan_digest=plan.plan_digest,
        checkpoints=receipts,
    )
