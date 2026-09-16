"""Terminal-independent preparation and execution of exact Memory edits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, overload

from memcommit.core.context_targeting.model import DirectMemoryLocator
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator


class EditError(RuntimeError):
    """Raised when an exact Edit cannot be prepared or published."""


@dataclass(frozen=True)
class EditRequest:
    memory_selector: str
    content: str
    context_locator: str | None = None


@dataclass(frozen=True)
class EditBatchRequest:
    """Ordered UID/content inputs belonging to one explicit or current Context."""

    edits: tuple[tuple[str, str], ...]
    context_locator: str | None = None
    input_source: str | None = None


EditTargetSelector = DirectMemoryLocator


@dataclass(frozen=True)
class EditMemoryChange:
    memory_uid: str
    original_content: str
    content: str

    @property
    def changed(self) -> bool:
        return self.original_content != self.content


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
class FrozenEditBatchPlan:
    request: EditBatchRequest
    context_name: str
    context_uid: str
    context_digest: str
    edits: tuple[EditMemoryChange, ...]
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


@dataclass(frozen=True)
class EditBatchResult:
    context_name: str
    context_uid: str
    edits: tuple[EditMemoryChange, ...]
    checkpoint_uid: str | None

    @property
    def changed_edits(self) -> tuple[EditMemoryChange, ...]:
        return tuple(edit for edit in self.edits if edit.changed)


class EditPort(Protocol):
    def freeze(
        self,
        request: EditRequest | EditBatchRequest,
    ) -> FrozenEditPlan | FrozenEditBatchPlan: ...

    def apply(
        self,
        plan: FrozenEditPlan | FrozenEditBatchPlan,
    ) -> EditResult | EditBatchResult: ...


def validate_edit_request(
    request: EditRequest | EditBatchRequest,
) -> EditRequest | EditBatchRequest:
    if not isinstance(request, (EditRequest, EditBatchRequest)):
        raise TypeError("Edit requires an EditRequest or EditBatchRequest.")
    if request.context_locator is not None and (
        not isinstance(request.context_locator, str) or not request.context_locator
    ):
        raise EditError("Edit Context locator must be nonempty text.")
    if isinstance(request, EditBatchRequest):
        if not isinstance(request.edits, tuple) or not request.edits:
            raise EditError("Edit batch requires at least one edit record.")
        if request.input_source is not None and (
            not isinstance(request.input_source, str) or not request.input_source
        ):
            raise EditError("Edit input source must be nonempty text.")
        entries = request.edits
    else:
        entries = ((request.memory_selector, request.content),)
    for entry in entries:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise EditError(
                "Each edit requires a Memory selector and replacement content."
            )
        selector, content = entry
        if not isinstance(selector, str) or not selector:
            raise EditError("Edit Memory selector must be nonempty text.")
        if not isinstance(content, str):
            raise EditError("Edit replacement content must be text.")
    return request


def edit_target_selector(request: EditRequest) -> EditTargetSelector:
    """Parse the shared ``CONTEXT:UID`` owner grammar for one Memory."""

    validate_edit_request(request)
    try:
        return parse_direct_memory_locator(
            request.memory_selector,
            explicit_context=request.context_locator,
        )
    except ValueError as error:
        raise EditError(str(error)) from error


def planned_edits(
    plan: FrozenEditPlan | FrozenEditBatchPlan,
) -> tuple[EditMemoryChange, ...]:
    if isinstance(plan, FrozenEditBatchPlan):
        return plan.edits
    return (
        EditMemoryChange(
            memory_uid=plan.memory_uid,
            original_content=plan.original_content,
            content=plan.request.content,
        ),
    )


def _validate_plan(
    request: EditRequest | EditBatchRequest,
    plan: FrozenEditPlan | FrozenEditBatchPlan,
) -> None:
    expected_type = (
        FrozenEditBatchPlan if isinstance(request, EditBatchRequest) else FrozenEditPlan
    )
    if not isinstance(plan, expected_type):
        raise TypeError("Edit port returned an invalid frozen plan.")
    if plan.request != request:
        raise EditError("Frozen Edit plan no longer matches the request.")
    if not all(
        isinstance(value, str) and value
        for value in (
            plan.context_name,
            plan.context_uid,
            plan.context_digest,
        )
    ):
        raise EditError("Edit plan has an incomplete binding.")
    edits = planned_edits(plan)
    contents = (
        tuple(content for _, content in request.edits)
        if isinstance(request, EditBatchRequest)
        else (request.content,)
    )
    if (
        not isinstance(edits, tuple)
        or len(edits) != len(contents)
        or any(not isinstance(edit, EditMemoryChange) for edit in edits)
        or any(
            not isinstance(edit.memory_uid, str)
            or not edit.memory_uid
            or not isinstance(edit.original_content, str)
            for edit in edits
        )
        or tuple(edit.content for edit in edits) != contents
        or len({edit.memory_uid for edit in edits}) != len(edits)
    ):
        raise EditError("Edit plan does not cover each requested Memory exactly once.")


@overload
def prepare_edit(request: EditRequest, *, port: EditPort) -> FrozenEditPlan: ...


@overload
def prepare_edit(
    request: EditBatchRequest, *, port: EditPort
) -> FrozenEditBatchPlan: ...


def prepare_edit(
    request: EditRequest | EditBatchRequest,
    *,
    port: EditPort,
) -> FrozenEditPlan | FrozenEditBatchPlan:
    validated = validate_edit_request(request)
    plan = port.freeze(validated)
    _validate_plan(validated, plan)
    return plan


@overload
def run_edit(
    request: EditRequest,
    *,
    port: EditPort,
    frozen_plan: FrozenEditPlan | None = None,
) -> EditResult: ...


@overload
def run_edit(
    request: EditBatchRequest,
    *,
    port: EditPort,
    frozen_plan: FrozenEditBatchPlan | None = None,
) -> EditBatchResult: ...


def run_edit(
    request: EditRequest | EditBatchRequest,
    *,
    port: EditPort,
    frozen_plan: FrozenEditPlan | FrozenEditBatchPlan | None = None,
) -> EditResult | EditBatchResult:
    validated = validate_edit_request(request)
    plan = (
        frozen_plan if frozen_plan is not None else prepare_edit(validated, port=port)
    )
    _validate_plan(validated, plan)
    result = port.apply(plan)
    expected_type = (
        EditBatchResult if isinstance(validated, EditBatchRequest) else EditResult
    )
    if not isinstance(result, expected_type):
        raise TypeError("Edit port returned an invalid durable receipt.")
    edits = planned_edits(plan)
    actual_edits = (
        result.edits
        if isinstance(result, EditBatchResult)
        else (
            EditMemoryChange(
                result.memory_uid, result.original_content, result.content
            ),
        )
    )
    changed = any(edit.changed for edit in edits)
    if (
        result.context_name != plan.context_name
        or result.context_uid != plan.context_uid
        or actual_edits != edits
        or (changed and not result.checkpoint_uid)
        or (not changed and result.checkpoint_uid is not None)
    ):
        raise EditError("Edit receipt does not match the frozen plan.")
    return result


__all__ = [
    "EditBatchRequest",
    "EditBatchResult",
    "EditError",
    "EditMemoryChange",
    "EditPort",
    "EditRequest",
    "EditResult",
    "EditTargetSelector",
    "FrozenEditBatchPlan",
    "FrozenEditPlan",
    "edit_target_selector",
    "planned_edits",
    "prepare_edit",
    "run_edit",
    "validate_edit_request",
]
