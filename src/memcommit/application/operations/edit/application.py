"""Prepare and execute one exact Memory replacement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class MemEditError(RuntimeError):
    """Raised when an exact Edit cannot be prepared or published."""


@dataclass(frozen=True)
class EditRequest:
    memory_selector: str
    content: str
    context_locator: str | None = None


@dataclass(frozen=True)
class FrozenEditPlan:
    request: EditRequest
    context_name: str
    context_uid: str
    memory_uid: str
    original_content: str
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class EditResult:
    context_name: str
    context_uid: str
    memory_uid: str
    original_content: str
    content: str
    checkpoint_uid: str | None

    @property
    def changed(self) -> bool:
        return self.original_content != self.content


class EditPort(Protocol):
    def freeze(self, request: EditRequest) -> FrozenEditPlan: ...

    def apply(self, plan: FrozenEditPlan) -> EditResult: ...


def validate_edit_request(request: EditRequest) -> EditRequest:
    if not isinstance(request, EditRequest):
        raise TypeError("Edit requires an EditRequest.")
    if request.context_locator is not None and (
        not isinstance(request.context_locator, str) or not request.context_locator
    ):
        raise MemEditError("Edit Context locator must be nonempty text.")
    if not isinstance(request.memory_selector, str) or not request.memory_selector:
        raise MemEditError("Edit Memory selector must be nonempty text.")
    if ":" in request.memory_selector:
        raise MemEditError("Edit accepts only a Memory UID in the current Context.")
    if not isinstance(request.content, str):
        raise MemEditError("Edit replacement content must be text.")
    return request


def _validate_plan(request: EditRequest, plan: FrozenEditPlan) -> None:
    if not isinstance(plan, FrozenEditPlan):
        raise TypeError("Edit port returned an invalid frozen plan.")
    if plan.request != request:
        raise MemEditError("Frozen Edit plan no longer matches the request.")
    if not all(
        isinstance(value, str) and value
        for value in (plan.context_name, plan.context_uid, plan.memory_uid)
    ) or not isinstance(plan.original_content, str):
        raise MemEditError("Edit plan has an incomplete binding.")


def prepare_edit(request: EditRequest, *, port: EditPort) -> FrozenEditPlan:
    validated = validate_edit_request(request)
    plan = port.freeze(validated)
    _validate_plan(validated, plan)
    return plan


def run_edit(
    request: EditRequest,
    *,
    port: EditPort,
    frozen_plan: FrozenEditPlan | None = None,
) -> EditResult:
    validated = validate_edit_request(request)
    plan = (
        frozen_plan if frozen_plan is not None else prepare_edit(validated, port=port)
    )
    _validate_plan(validated, plan)
    result = port.apply(plan)
    if not isinstance(result, EditResult):
        raise TypeError("Edit port returned an invalid durable receipt.")
    changed = plan.original_content != validated.content
    if (
        result.context_name != plan.context_name
        or result.context_uid != plan.context_uid
        or result.memory_uid != plan.memory_uid
        or result.original_content != plan.original_content
        or result.content != validated.content
        or (changed and not result.checkpoint_uid)
        or (not changed and result.checkpoint_uid is not None)
    ):
        raise MemEditError("Edit receipt does not match the frozen plan.")
    return result


__all__ = [
    "MemEditError",
    "EditPort",
    "EditRequest",
    "EditResult",
    "FrozenEditPlan",
    "prepare_edit",
    "run_edit",
    "validate_edit_request",
]
