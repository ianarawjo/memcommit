"""Application boundary for moving exact Memories between local Contexts."""

from __future__ import annotations

from typing import Protocol

from memcommit.application.operations.copy_and_move.application import (
    FrozenMoveMemoriesPlan,
    MemoryTransferAuthorityError,
    MemoryTransferError,
    MemoryTransferItemResult,
    MoveMemoriesRequest,
    MoveMemoriesResult,
    _validate_plan_common,
    validate_move_request,
)


class MovePort(Protocol):
    def freeze_move(self, request: MoveMemoriesRequest) -> FrozenMoveMemoriesPlan: ...

    def apply_move(self, plan: FrozenMoveMemoriesPlan) -> MoveMemoriesResult: ...


def _validate_move_plan(plan: FrozenMoveMemoriesPlan) -> None:
    _validate_plan_common(
        plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
        placement=plan.placement,
        plan_digest=plan.plan_digest,
    )
    if any(item.output_memory_uid != item.source_memory_uid for item in plan.memories):
        raise MemoryTransferError("Move must preserve every selected Memory UID.")
    if any(item.source_authority is not None for item in plan.memories):
        raise MemoryTransferAuthorityError(
            "Move cannot use granted Source Memories; Copy them into a local "
            "Context first, then move the local copies."
        )
    if len({item.output_memory_uid for item in plan.memories}) != len(plan.memories):
        raise MemoryTransferError(
            "Move cannot place same-UID branch copies in one Target Context."
        )


def prepare_move(
    request: MoveMemoriesRequest,
    *,
    port: MovePort,
) -> FrozenMoveMemoriesPlan:
    request = validate_move_request(request)
    plan = port.freeze_move(request)
    if not isinstance(plan, FrozenMoveMemoriesPlan):
        raise TypeError("Move port returned an invalid frozen plan.")
    if plan.request != request:
        raise MemoryTransferError("Move plan does not describe the request.")
    _validate_move_plan(plan)
    return plan


def run_move(
    request: MoveMemoriesRequest,
    *,
    port: MovePort,
    frozen_plan: FrozenMoveMemoriesPlan | None = None,
) -> MoveMemoriesResult:
    request = validate_move_request(request)
    plan = frozen_plan or prepare_move(request, port=port)
    if not isinstance(plan, FrozenMoveMemoriesPlan) or plan.request != request:
        raise MemoryTransferError("Frozen Move plan no longer matches the request.")
    _validate_move_plan(plan)
    result = port.apply_move(plan)
    if not isinstance(result, MoveMemoriesResult):
        raise TypeError("Move port returned an invalid durable receipt.")
    expected = tuple(
        MemoryTransferItemResult(
            source_context_name=item.source_context_name,
            source_context_uid=item.source_context_uid,
            source_memory_uid=item.source_memory_uid,
            into_memory_uid=item.output_memory_uid,
        )
        for item in plan.memories
    )
    inbound_count = len(plan.inbound_links)
    expected_retargeted = inbound_count if request.link_policy == "RETARGET" else 0
    expected_dangling = inbound_count if request.link_policy == "BREAK" else 0
    if (
        result.into_name != plan.into_name
        or result.into_uid != plan.into_uid
        or result.link_policy != request.link_policy
        or result.placement != plan.placement
        or result.items != expected
        or result.inbound_link_count != inbound_count
        or result.retargeted_link_count != expected_retargeted
        or result.dangling_link_count != expected_dangling
        or result.plan_digest != plan.plan_digest
        or not result.checkpoints
    ):
        raise MemoryTransferError("Move receipt does not match the frozen plan.")
    return result


__all__ = ["MovePort", "prepare_move", "run_move"]
