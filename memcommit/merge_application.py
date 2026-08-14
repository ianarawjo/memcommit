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
class MergeContextResult:
    """One relative-path Source/Target pair in a structural Merge plan."""

    source_name: str
    source_uid: str
    target_name: str
    target_uid: str
    target_created: bool
    additions: tuple[MergeAddition, ...]

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (
                self.source_name,
                self.source_uid,
                self.target_name,
                self.target_uid,
            )
        ):
            raise ValueError("Merge Context result has an incomplete identity.")
        if type(self.target_created) is not bool:
            raise TypeError("Merge target-created state must be a boolean.")
        if any(not isinstance(value, MergeAddition) for value in self.additions):
            raise TypeError("Merge Context additions must be MergeAddition values.")


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
    contexts: tuple[MergeContextResult, ...]
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
    contexts: tuple[MergeContextResult, ...]
    checkpoint_uid: str
    checkpoint_uids: tuple[str, ...]
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
    if not plan.contexts:
        raise MergeError("Merge plan must contain at least one Context pair.")
    root = plan.contexts[0]
    if (
        root.source_name != plan.source_name
        or root.source_uid != plan.source_uid
        or root.target_name != plan.target_name
        or root.target_uid != plan.target_uid
    ):
        raise MergeError("Merge root pair does not match the frozen plan.")
    if (
        tuple(addition for context in plan.contexts for addition in context.additions)
        != plan.additions
    ):
        raise MergeError("Merge plan additions do not cover its Context pairs.")
    if plan.request.reach is MergeReach.DIRECT and len(plan.contexts) != 1:
        raise MergeError("Direct Merge must contain exactly one Context pair.")
    if len({context.source_name for context in plan.contexts}) != len(plan.contexts):
        raise MergeError("Merge plan repeats a Source Context.")
    if len({context.target_name for context in plan.contexts}) != len(plan.contexts):
        raise MergeError("Merge plan repeats a Target Context.")
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
        or result.contexts != plan.contexts
        or result.cross_profile_memory_only != plan.cross_profile_memory_only
        or not result.checkpoint_uid
        or not result.checkpoint_uids
        or result.checkpoint_uid != result.checkpoint_uids[0]
        or len(result.checkpoint_uids) != len(result.contexts)
        or len(set(result.checkpoint_uids)) != len(result.checkpoint_uids)
    ):
        raise MergeError("Merge receipt does not match the frozen plan.")
    return result
