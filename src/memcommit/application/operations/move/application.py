"""Application boundary for moving exact Memories between local Contexts."""

from __future__ import annotations

from typing import Protocol

from memcommit.application.capabilities.memory_transfer.contracts import (
    MemoryTransferError,
    MemoryTransferItemResult,
    validate_transfer_plan_fields,
    validate_transfer_request_fields,
)
from memcommit.application.operations.move.contracts import (
    FrozenMoveMemoriesPlan,
    MoveMemoriesRequest,
    MoveMemoriesResult,
)


def validate_move_request(request: MoveMemoriesRequest) -> MoveMemoriesRequest:
    if not isinstance(request, MoveMemoriesRequest):
        raise TypeError("Move requires a MoveMemoriesRequest.")
    validate_transfer_request_fields(
        request.memory_locators,
        into_locator=request.into_locator,
        source_locator=request.source_locator,
        before=request.before,
        after=request.after,
    )
    return request


class MovePort(Protocol):
    def freeze_move(self, request: MoveMemoriesRequest) -> FrozenMoveMemoriesPlan: ...

    def apply_move(self, plan: FrozenMoveMemoriesPlan) -> MoveMemoriesResult: ...


def _validate_move_plan(plan: FrozenMoveMemoriesPlan) -> None:
    validate_transfer_plan_fields(
        plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        placement=plan.placement,
        plan_digest=plan.plan_digest,
    )
    if any(item.output_memory_uid != item.source_memory_uid for item in plan.memories):
        raise MemoryTransferError("Move must preserve every selected Memory UID.")
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
    if (
        result.into_name != plan.into_name
        or result.into_uid != plan.into_uid
        or result.placement != plan.placement
        or result.items != expected
        or result.plan_digest != plan.plan_digest
        or not result.checkpoints
    ):
        raise MemoryTransferError("Move receipt does not match the frozen plan.")
    return result


__all__ = ["validate_move_request", "MovePort", "prepare_move", "run_move"]
