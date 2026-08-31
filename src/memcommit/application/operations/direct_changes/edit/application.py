"""Terminal-independent contract for one exact direct-Memory edit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from memcommit.core.context_targeting.model import DirectMemoryLocator
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator


class EditError(RuntimeError):
    """Raised when an exact Edit cannot be prepared or published."""


@dataclass(frozen=True)
class EditRequest:
    memory_selector: str
    content: str
    context_locator: str | None = None


EditTargetSelector = DirectMemoryLocator


@dataclass(frozen=True)
class FrozenEditPlan:
    request: EditRequest
    context_name: str
    context_uid: str
    context_digest: str
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
    if not isinstance(request.memory_selector, str) or not request.memory_selector:
        raise EditError("Edit Memory selector must be nonempty text.")
    if not isinstance(request.content, str):
        raise EditError("Edit replacement content must be text.")
    if request.context_locator is not None and (
        not isinstance(request.context_locator, str) or not request.context_locator
    ):
        raise EditError("Edit Context locator must be nonempty text.")
    return request


def edit_target_selector(request: EditRequest) -> EditTargetSelector:
    """Parse the shared ``CONTEXT:UID`` owner grammar for Edit."""

    request = validate_edit_request(request)
    try:
        return parse_direct_memory_locator(
            request.memory_selector,
            explicit_context=request.context_locator,
        )
    except ValueError as error:
        raise EditError(str(error)) from error


def prepare_edit(request: EditRequest, *, port: EditPort) -> FrozenEditPlan:
    validated = validate_edit_request(request)
    plan = port.freeze(validated)
    if not isinstance(plan, FrozenEditPlan):
        raise TypeError("Edit port returned an invalid frozen plan.")
    if plan.request != validated:
        raise EditError("Edit plan does not describe the request.")
    if not all(
        (
            plan.context_name,
            plan.context_uid,
            plan.context_digest,
            plan.memory_uid,
        )
    ):
        raise EditError("Edit plan has an incomplete binding.")
    return plan


def run_edit(
    request: EditRequest,
    *,
    port: EditPort,
    frozen_plan: FrozenEditPlan | None = None,
) -> EditResult:
    validated = validate_edit_request(request)
    plan = frozen_plan or prepare_edit(validated, port=port)
    if not isinstance(plan, FrozenEditPlan):
        raise TypeError("Edit requires a valid frozen plan.")
    if plan.request != validated:
        raise EditError("Frozen Edit plan no longer matches the request.")
    result = port.apply(plan)
    if not isinstance(result, EditResult):
        raise TypeError("Edit port returned an invalid durable receipt.")
    if (
        result.context_name != plan.context_name
        or result.context_uid != plan.context_uid
        or result.memory_uid != plan.memory_uid
        or result.original_content != plan.original_content
        or result.content != validated.content
        or (result.changed and not result.checkpoint_uid)
        or (not result.changed and result.checkpoint_uid is not None)
    ):
        raise EditError("Edit receipt does not match the frozen plan.")
    return result


__all__ = [
    "EditError",
    "EditPort",
    "EditRequest",
    "EditResult",
    "EditTargetSelector",
    "FrozenEditPlan",
    "edit_target_selector",
    "prepare_edit",
    "run_edit",
    "validate_edit_request",
]
