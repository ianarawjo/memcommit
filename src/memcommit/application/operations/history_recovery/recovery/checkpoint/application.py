"""Typed plan-and-apply boundary for manual Checkpoint creation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CheckpointRequest:
    """One command-start-stable manual Checkpoint request."""

    context_locator: str | None
    current_context_name: str | None
    message: str = ""
    recursive: bool = False

    def __post_init__(self) -> None:
        if self.context_locator is not None and (
            not isinstance(self.context_locator, str) or not self.context_locator
        ):
            raise ValueError("Checkpoint Context locator must be nonblank text.")
        if self.current_context_name is not None and (
            not isinstance(self.current_context_name, str)
            or not self.current_context_name
        ):
            raise ValueError("Checkpoint current Context must be nonblank text.")
        if not isinstance(self.message, str):
            raise TypeError("Checkpoint message must be text.")
        if not isinstance(self.recursive, bool):
            raise TypeError("Checkpoint recursive scope must be boolean.")


@dataclass(frozen=True, slots=True)
class CheckpointMemberPlan:
    """One exact Context member of a frozen Checkpoint plan."""

    context_name: str
    context_uid: str
    context_digest: str
    checkpoint_uid: str | None


@dataclass(frozen=True, slots=True)
class CheckpointPlan:
    """One frozen direct or recursive Checkpoint publication plan."""

    request: CheckpointRequest
    root_context_name: str
    root_context_uid: str
    members: tuple[CheckpointMemberPlan, ...]
    expected_context_catalog: tuple[str, ...] | None
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("Checkpoint plan requires at least one Context.")
        if self.members[0].context_name != self.root_context_name:
            raise ValueError("Checkpoint plan root must be its first member.")
        if self.members[0].context_uid != self.root_context_uid:
            raise ValueError("Checkpoint plan root identity is inconsistent.")
        if len({member.context_name for member in self.members}) != len(self.members):
            raise ValueError("Checkpoint plan repeats a Context name.")
        if self.request.recursive:
            checkpoint_uids = tuple(
                member.checkpoint_uid for member in self.members
            )
            if (
                self.expected_context_catalog is None
                or any(uid is None for uid in checkpoint_uids)
                or len(checkpoint_uids) != len(set(checkpoint_uids))
            ):
                raise ValueError("Recursive Checkpoint plan is incomplete.")
        elif len(self.members) != 1 or self.expected_context_catalog is not None:
            raise ValueError("Direct Checkpoint plan must contain only its root.")


@dataclass(frozen=True, slots=True)
class CheckpointResult:
    """Presentation-safe receipt from one manual Checkpoint operation."""

    root_context_name: str
    root_checkpoint_uid: str
    timestamp: datetime
    message: str
    recursive: bool
    member_count: int

    def __post_init__(self) -> None:
        if not self.root_context_name or not self.root_checkpoint_uid:
            raise ValueError("Checkpoint result identity is incomplete.")
        if self.member_count < 1:
            raise ValueError("Checkpoint result requires at least one member.")
        if not self.recursive and self.member_count != 1:
            raise ValueError("Direct Checkpoint result must have one member.")


class CheckpointPort(Protocol):
    """Application effects required by manual Checkpoint creation."""

    def freeze(self, request: CheckpointRequest) -> CheckpointPlan: ...

    def apply(self, plan: CheckpointPlan) -> CheckpointResult: ...


def plan_checkpoint(
    request: CheckpointRequest,
    *,
    port: CheckpointPort,
) -> CheckpointPlan:
    """Freeze one exact manual Checkpoint request."""

    if not isinstance(request, CheckpointRequest):
        raise TypeError("Checkpoint requires a CheckpointRequest.")
    plan = port.freeze(request)
    if not isinstance(plan, CheckpointPlan) or plan.request != request:
        raise TypeError("Checkpoint port returned an invalid plan.")
    return plan


def apply_checkpoint(
    plan: CheckpointPlan,
    *,
    port: CheckpointPort,
) -> CheckpointResult:
    """Publish one previously frozen manual Checkpoint plan."""

    if not isinstance(plan, CheckpointPlan):
        raise TypeError("Checkpoint Apply requires a CheckpointPlan.")
    result = port.apply(plan)
    if not isinstance(result, CheckpointResult):
        raise TypeError("Checkpoint port returned an invalid result.")
    if (
        result.root_context_name != plan.root_context_name
        or result.message != plan.request.message
        or result.recursive is not plan.request.recursive
        or result.member_count != len(plan.members)
    ):
        raise RuntimeError("Checkpoint result does not match its frozen plan.")
    return result


__all__ = [
    "CheckpointMemberPlan",
    "CheckpointPlan",
    "CheckpointPort",
    "CheckpointRequest",
    "CheckpointResult",
    "apply_checkpoint",
    "plan_checkpoint",
]
