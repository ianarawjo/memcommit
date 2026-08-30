"""Terminal-independent plan and apply boundary for Context Rename."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RenameRequest:
    old_locator: str
    new_name: str
    current_context_name: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.old_locator, str) or not self.old_locator:
            raise ValueError("Rename source locator must be nonblank text.")
        if not isinstance(self.new_name, str) or not self.new_name:
            raise ValueError("Rename destination name must be nonblank text.")


@dataclass(frozen=True, slots=True)
class RenameBinding:
    old_name: str
    new_name: str
    context_uid: str


@dataclass(frozen=True, slots=True)
class RenamePlan:
    old_name: str
    new_name: str
    bindings: tuple[RenameBinding, ...]
    changed_owner_count: int
    reference_count: int
    checkpoint_reference_count: int
    translation_artifact_count: int
    meld_session_count: int
    current_before: str | None
    current_after: str | None
    graph_digest: str
    token: object = field(repr=False, compare=False)

    @property
    def descendant_count(self) -> int:
        return max(0, len(self.bindings) - 1)


@dataclass(frozen=True, slots=True)
class RenameResult:
    old_name: str
    new_name: str
    renamed_context_count: int
    changed_owner_count: int
    reference_count: int
    checkpoint_reference_count: int
    translation_artifact_count: int
    meld_session_count: int
    current_context: str | None


class RenamePort(Protocol):
    def freeze(self, request: RenameRequest) -> RenamePlan: ...

    def apply(self, plan: RenamePlan) -> RenameResult: ...


def plan_rename(request: RenameRequest, *, port: RenamePort) -> RenamePlan:
    if not isinstance(request, RenameRequest):
        raise TypeError("Rename requires a RenameRequest.")
    plan = port.freeze(request)
    if not isinstance(plan, RenamePlan):
        raise TypeError("Rename port returned an invalid plan.")
    return plan


def apply_rename(plan: RenamePlan, *, port: RenamePort) -> RenameResult:
    if not isinstance(plan, RenamePlan):
        raise TypeError("Rename Apply requires a RenamePlan.")
    result = port.apply(plan)
    if not isinstance(result, RenameResult):
        raise TypeError("Rename port returned an invalid result.")
    if (result.old_name, result.new_name) != (plan.old_name, plan.new_name):
        raise RuntimeError("Rename result does not match its reviewed plan.")
    return result


__all__ = [
    "RenameBinding",
    "RenamePlan",
    "RenamePort",
    "RenameRequest",
    "RenameResult",
    "apply_rename",
    "plan_rename",
]

