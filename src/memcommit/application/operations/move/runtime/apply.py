"""Apply one frozen Move plan through the Store command-batch boundary."""

from __future__ import annotations

from memcommit.application.capabilities.memory_transfer.checkpoint_metadata import (
    transfer_checkpoint_metadata,
)
from memcommit.application.capabilities.memory_transfer.context_bindings import (
    validate_context_bindings,
)
from memcommit.application.capabilities.memory_transfer.contracts import (
    MemoryTransferCheckpoint,
    MemoryTransferStalePlanError,
    transfer_item_results,
)
from memcommit.application.operations.move.contracts import (
    FrozenMoveMemoriesPlan,
    MoveMemoriesResult,
)
from memcommit.application.operations.move.runtime.prepare import move_plan_digest
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.memory import Memory
from memcommit.persistence.store import ConcurrentContextUpdateError, ProfileStore


def apply_move(
    plan: FrozenMoveMemoriesPlan,
    *,
    store: ProfileStore,
    owner: object,
) -> MoveMemoriesResult:
    if not isinstance(plan, FrozenMoveMemoriesPlan):
        raise TypeError("Move requires its own frozen plan.")
    bindings = plan.token
    token = validate_context_bindings(
        bindings,
        owner=owner,
        plan_digest=plan.plan_digest,
        expected_plan_digest=move_plan_digest(plan),
        memories=plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
    )
    frames = {frame.display_name: frame for frame in token.frames}
    into = frames[plan.into_name]
    for item in plan.memories:
        frames[item.source_context_name].context.remove(item.source_memory_uid)

    for offset, item in enumerate(plan.memories):
        into.context.add(
            Memory(uid=item.source_memory_uid, content=item.content),
            position=plan.placement.position + offset,
        )

    affected_names = list(
        dict.fromkeys(
            [
                *(item.source_context_name for item in plan.memories),
                plan.into_name,
            ]
        )
    )
    affected = tuple(frames[name] for name in sorted(affected_names))
    args = transfer_checkpoint_metadata(
        kind="MOVE",
        operation_uid=token.operation_uid,
        plan_digest=plan.plan_digest,
        policy_name="move_identity",
        policy="PRESERVE_UIDS",
        into_name=into.context.name,
        into_uid=into.context.uid,
        placement=plan.placement,
        memories=plan.memories,
        affected_contexts=tuple(
            (frame.context.name, frame.context.uid) for frame in affected
        ),
    )
    entries = tuple(
        (
            frame.context,
            AutoCheckpointRequest(command="move", command_details=args),
        )
        for frame in affected
    )
    try:
        checkpoints = store.save_context_command_batch(
            entries,
            source_bindings=tuple(
                (
                    frame.context.name,
                    frame.context.uid,
                )
                for frame in token.frames
            ),
            expected_context_catalog=token.context_catalog,
        )
    except ConcurrentContextUpdateError as error:
        raise MemoryTransferStalePlanError(
            "Move Source or Target changed before publication; nothing was moved."
        ) from error
    receipts = tuple(
        MemoryTransferCheckpoint(
            context_name=frame.context.name,
            context_uid=frame.context.uid,
            checkpoint_uid=checkpoint.uid,
        )
        for frame, checkpoint in zip(affected, checkpoints, strict=True)
    )
    return MoveMemoriesResult(
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        placement=plan.placement,
        items=transfer_item_results(plan.memories),
        plan_digest=plan.plan_digest,
        checkpoints=receipts,
    )
