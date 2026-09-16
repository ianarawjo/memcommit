"""Application boundary for copying exact Memories into a local Context."""

from __future__ import annotations

from typing import Protocol

from memcommit.application.capabilities.memory_transfer.contracts import (
    MemoryTransferError,
    MemoryTransferItemResult,
    validate_transfer_plan_fields,
    validate_transfer_request_fields,
)
from memcommit.application.operations.copy.contracts import (
    CopyMemoriesRequest,
    CopyMemoriesResult,
    FrozenCopyMemoriesPlan,
)


def validate_copy_request(request: CopyMemoriesRequest) -> CopyMemoriesRequest:
    if not isinstance(request, CopyMemoriesRequest):
        raise TypeError("Copy requires a CopyMemoriesRequest.")
    validate_transfer_request_fields(
        request.memory_locators,
        into_locator=request.into_locator,
        source_locator=request.source_locator,
        before=request.before,
        after=request.after,
    )
    return request


class CopyPort(Protocol):
    def freeze_copy(self, request: CopyMemoriesRequest) -> FrozenCopyMemoriesPlan: ...

    def apply_copy(self, plan: FrozenCopyMemoriesPlan) -> CopyMemoriesResult: ...


def prepare_copy(
    request: CopyMemoriesRequest,
    *,
    port: CopyPort,
) -> FrozenCopyMemoriesPlan:
    request = validate_copy_request(request)
    plan = port.freeze_copy(request)
    if not isinstance(plan, FrozenCopyMemoriesPlan):
        raise TypeError("Copy port returned an invalid frozen plan.")
    if plan.request != request:
        raise MemoryTransferError("Copy plan does not describe the request.")
    validate_transfer_plan_fields(
        plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
        placement=plan.placement,
        plan_digest=plan.plan_digest,
    )
    if len({item.output_memory_uid for item in plan.memories}) != len(plan.memories):
        raise MemoryTransferError("Copy plan has duplicate output Memory UIDs.")
    return plan


def run_copy(
    request: CopyMemoriesRequest,
    *,
    port: CopyPort,
    frozen_plan: FrozenCopyMemoriesPlan | None = None,
) -> CopyMemoriesResult:
    request = validate_copy_request(request)
    plan = frozen_plan or prepare_copy(request, port=port)
    if not isinstance(plan, FrozenCopyMemoriesPlan) or plan.request != request:
        raise MemoryTransferError("Frozen Copy plan no longer matches the request.")
    validate_transfer_plan_fields(
        plan.memories,
        into_name=plan.into_name,
        into_uid=plan.into_uid,
        into_digest=plan.into_digest,
        placement=plan.placement,
        plan_digest=plan.plan_digest,
    )
    if len({item.output_memory_uid for item in plan.memories}) != len(plan.memories):
        raise MemoryTransferError("Copy plan has duplicate output Memory UIDs.")
    result = port.apply_copy(plan)
    if not isinstance(result, CopyMemoriesResult):
        raise TypeError("Copy port returned an invalid durable receipt.")
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
        raise MemoryTransferError("Copy receipt does not match the frozen plan.")
    return result


__all__ = ["validate_copy_request", "CopyPort", "prepare_copy", "run_copy"]
