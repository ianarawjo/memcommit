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
from memcommit.application.operations.move.runtime.live_embeds import (
    inbound_link_checkpoint_values,
    retarget_live_embeds,
)
from memcommit.application.operations.move.runtime.prepare import move_plan_digest
from memcommit.core.context import AutoCheckpoint, Memory
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def apply_move(
    plan: FrozenMoveMemoriesPlan,
    *,
    store: MemoryStore,
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
        into_digest=plan.into_digest,
    )
    frames = {frame.display_name: frame for frame in token.frames}
    into = frames[plan.into_name]
    for item in plan.memories:
        frames[item.source_context_name].context.remove(item.source_memory_uid)

    retarget_live_embeds(
        frames,
        into=into,
        memories=plan.memories,
        inbound_links=plan.inbound_links,
        policy=plan.request.link_policy,
    )

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
                *(
                    link.owner_context_name
                    for link in plan.inbound_links
                    if plan.request.link_policy == "RETARGET"
                ),
            ]
        )
    )
    affected = tuple(frames[name] for name in sorted(affected_names))
    description = (
        f"Moved {len(plan.memories)} Memory/ies into '{plan.into_name}' "
        f"with {plan.request.link_policy.lower()} live-link policy."
    )
    args = transfer_checkpoint_metadata(
        kind="MOVE",
        operation_uid=token.operation_uid,
        plan_digest=plan.plan_digest,
        policy_name="link_policy",
        policy=plan.request.link_policy,
        into_name=into.context.name,
        into_uid=into.context.uid,
        placement=plan.placement,
        memories=plan.memories,
        inbound_links=inbound_link_checkpoint_values(plan.inbound_links),
        affected_contexts=tuple(
            (frame.context.name, frame.context.uid) for frame in affected
        ),
    )
    entries = tuple(
        (
            frame.context,
            AutoCheckpoint(command="move", args=args, description=description),
            frame.expected_digest,
        )
        for frame in affected
    )
    try:
        checkpoints = store.save_context_command_batch(
            entries,
            # Move's default safety claim depends on the absence or exact
            # disposition of every local inbound live Embed. Bind the full
            # scanned graph until every affected Context has committed.
            source_bindings=tuple(
                (
                    frame.context.name,
                    frame.context.uid,
                    frame.expected_digest,
                )
                for frame in token.frames
            ),
            expected_context_catalog=token.context_catalog,
        )
    except ConcurrentContextUpdateError as error:
        raise MemoryTransferStalePlanError(
            "Move Source, Target, or inbound-link graph changed before "
            "publication; nothing was moved."
        ) from error
    receipts = tuple(
        MemoryTransferCheckpoint(
            context_name=frame.context.name,
            context_uid=frame.context.uid,
            checkpoint_uid=checkpoint.uid,
        )
        for frame, checkpoint in zip(affected, checkpoints, strict=True)
    )
    inbound_count = len(plan.inbound_links)
    return MoveMemoriesResult(
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        link_policy=plan.request.link_policy,
        placement=plan.placement,
        items=transfer_item_results(plan.memories),
        inbound_link_count=inbound_count,
        retargeted_link_count=(
            inbound_count if plan.request.link_policy == "RETARGET" else 0
        ),
        dangling_link_count=(
            inbound_count if plan.request.link_policy == "BREAK" else 0
        ),
        plan_digest=plan.plan_digest,
        checkpoints=receipts,
    )
