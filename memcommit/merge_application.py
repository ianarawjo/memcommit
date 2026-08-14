"""Terminal-independent application contract for structural Context Merge."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class MergeError(RuntimeError):
    """Raised when one Merge request cannot be completed atomically."""


class MergeReach(str, Enum):
    """Lexical reach selected for one structural Merge."""

    DIRECT = "DIRECT"
    DESCENDANTS = "DESCENDANTS"


class MergeItemKind(str, Enum):
    """Durable direct-item kinds reported without exposing Store objects."""

    MEMORY = "MEMORY"
    MEMORY_REF = "MEMORY_REF"
    QUERY_VIEW = "QUERY_VIEW"
    CONTEXT = "CONTEXT"


@dataclass(frozen=True)
class MergeRequest:
    """One stable Merge request independent of argv and terminal state."""

    source_locator: str
    target_locator: str | None = None
    reach: MergeReach = MergeReach.DIRECT


@dataclass(frozen=True)
class MergeAddition:
    """One direct item newly added to the Target."""

    uid: str
    kind: MergeItemKind

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid:
            raise ValueError("Merge addition UID must be nonempty text.")
        if not isinstance(self.kind, MergeItemKind):
            raise TypeError("Merge addition kind must be a MergeItemKind.")


@dataclass(frozen=True)
class FrozenMergePlan:
    """Reviewed identities and additions plus an opaque Store binding."""

    request: MergeRequest
    source_name: str
    source_uid: str
    source_digest: str
    target_name: str
    target_uid: str
    target_digest: str
    additions: tuple[MergeAddition, ...]
    cross_profile_memory_only: bool
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class MergeResult:
    """Typed durable receipt shared by CLI and future public adapters."""

    source_name: str
    source_uid: str
    target_name: str
    target_uid: str
    reach: MergeReach
    additions: tuple[MergeAddition, ...]
    checkpoint_uid: str
    cross_profile_memory_only: bool

    def count(self, kind: MergeItemKind) -> int:
        """Count newly added direct items of one kind."""

        return sum(addition.kind is kind for addition in self.additions)


class MergePort(Protocol):
    """Freeze and atomically apply one authorized structural Merge."""

    def freeze(self, request: MergeRequest) -> FrozenMergePlan:
        """Resolve and plan one Merge without changing durable state."""

    def apply(self, plan: FrozenMergePlan) -> MergeResult:
        """Commit the frozen plan or publish none of it."""


def validate_merge_request(request: MergeRequest) -> MergeRequest:
    """Validate adapter-independent input before opening a Store."""

    if not isinstance(request, MergeRequest):
        raise TypeError("Merge requires a MergeRequest.")
    if not isinstance(request.source_locator, str) or not request.source_locator:
        raise MergeError("Merge Source locator must be nonempty text.")
    if request.target_locator is not None and (
        not isinstance(request.target_locator, str) or not request.target_locator
    ):
        raise MergeError("Merge Target locator must be nonempty text.")
    if not isinstance(request.reach, MergeReach):
        raise MergeError("Merge reach is invalid.")
    if request.reach is not MergeReach.DIRECT:
        raise MergeError("Descendant Merge is not available yet.")
    return request


def prepare_merge(
    request: MergeRequest,
    *,
    port: MergePort,
) -> FrozenMergePlan:
    """Freeze one reviewable Merge plan without durable mutation."""

    validated = validate_merge_request(request)
    plan = port.freeze(validated)
    if not isinstance(plan, FrozenMergePlan):
        raise TypeError("Merge port returned an invalid frozen plan.")
    if plan.request != validated:
        raise MergeError("Merge plan does not describe the requested operation.")
    if not all(
        (
            plan.source_name,
            plan.source_uid,
            plan.source_digest,
            plan.target_name,
            plan.target_uid,
            plan.target_digest,
        )
    ):
        raise MergeError("Merge plan has an incomplete Context binding.")
    if plan.source_uid == plan.target_uid and plan.source_name == plan.target_name:
        raise MergeError("Merge plan cannot target its own Source.")
    return plan


def run_merge(
    request: MergeRequest,
    *,
    port: MergePort,
    frozen_plan: FrozenMergePlan | None = None,
) -> MergeResult:
    """Apply one structural Merge without CLI, TUI, or provider dependencies."""

    validated = validate_merge_request(request)
    plan = frozen_plan or prepare_merge(validated, port=port)
    if not isinstance(plan, FrozenMergePlan):
        raise TypeError("Merge requires a valid frozen plan.")
    if plan.request != validated:
        raise MergeError("The frozen Merge plan no longer matches the request.")
    result = port.apply(plan)
    if not isinstance(result, MergeResult):
        raise TypeError("Merge port returned an invalid durable receipt.")
    if (
        result.source_name != plan.source_name
        or result.source_uid != plan.source_uid
        or result.target_name != plan.target_name
        or result.target_uid != plan.target_uid
        or result.reach is not plan.request.reach
        or result.additions != plan.additions
        or result.cross_profile_memory_only != plan.cross_profile_memory_only
        or not result.checkpoint_uid
    ):
        raise MergeError("Merge receipt does not match the frozen plan.")
    return result
