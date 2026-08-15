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


class MergeConflictKind(str, Enum):
    """Deterministic reasons why one Source item cannot be added as-is."""

    CONTENT_DIVERGENCE = "CONTENT_DIVERGENCE"
    TYPE_COLLISION = "TYPE_COLLISION"
    REFERENCE_COLLISION = "REFERENCE_COLLISION"
    PLACEMENT_COLLISION = "PLACEMENT_COLLISION"


class MergeDecision(str, Enum):
    """The complete deterministic resolution vocabulary for Merge."""

    KEEP_TARGET = "KEEP_TARGET"
    TAKE_SOURCE = "TAKE_SOURCE"


@dataclass(frozen=True)
class MergeItemSnapshot:
    """Review-safe direct-item evidence without a live Store object."""

    uid: str
    kind: MergeItemKind
    description: str
    content: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid:
            raise ValueError("Merge item snapshot UID must be nonempty text.")
        if not isinstance(self.kind, MergeItemKind):
            raise TypeError("Merge item snapshot kind is invalid.")
        if not isinstance(self.description, str) or not self.description:
            raise ValueError("Merge item snapshot description must be nonempty text.")
        if self.content is not None and not isinstance(self.content, str):
            raise TypeError("Merge item snapshot content must be text or None.")


@dataclass(frozen=True)
class MergeConflict:
    """One mapping-qualified required deterministic Merge decision."""

    uid: str
    kind: MergeConflictKind
    source_name: str
    target_name: str
    source: MergeItemSnapshot
    targets: tuple[MergeItemSnapshot, ...]
    reason: str
    allowed_decisions: tuple[MergeDecision, ...] = (
        MergeDecision.KEEP_TARGET,
        MergeDecision.TAKE_SOURCE,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid:
            raise ValueError("Merge conflict UID must be nonempty text.")
        if not isinstance(self.kind, MergeConflictKind):
            raise TypeError("Merge conflict kind is invalid.")
        if not self.source_name or not self.target_name:
            raise ValueError("Merge conflict mapping is incomplete.")
        if not isinstance(self.source, MergeItemSnapshot):
            raise TypeError("Merge conflict Source evidence is invalid.")
        if not self.targets or any(
            not isinstance(item, MergeItemSnapshot) for item in self.targets
        ):
            raise TypeError("Merge conflict Target evidence is invalid.")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("Merge conflict reason must be nonempty text.")
        if (
            not self.allowed_decisions
            or len(set(self.allowed_decisions)) != len(self.allowed_decisions)
            or any(
                not isinstance(decision, MergeDecision)
                for decision in self.allowed_decisions
            )
            or MergeDecision.KEEP_TARGET not in self.allowed_decisions
        ):
            raise ValueError("Merge conflict allowed decisions are invalid.")


@dataclass(frozen=True)
class MergeResolution:
    """One exact answer for a frozen mapping-qualified conflict."""

    conflict_uid: str
    decision: MergeDecision

    def __post_init__(self) -> None:
        if not isinstance(self.conflict_uid, str) or not self.conflict_uid:
            raise ValueError("Merge resolution conflict UID must be nonempty text.")
        if not isinstance(self.decision, MergeDecision):
            raise TypeError("Merge resolution decision is invalid.")


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
    unchanged: tuple[MergeItemSnapshot, ...] = ()
    conflicts: tuple[MergeConflict, ...] = ()

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
        if any(
            not isinstance(value, MergeItemSnapshot) for value in self.unchanged
        ):
            raise TypeError("Merge Context unchanged items are invalid.")
        if any(not isinstance(value, MergeConflict) for value in self.conflicts):
            raise TypeError("Merge Context conflicts are invalid.")


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
    mutates_granted_authority: bool = False
    unchanged: tuple[MergeItemSnapshot, ...] = ()
    conflicts: tuple[MergeConflict, ...] = ()


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
    unchanged: tuple[MergeItemSnapshot, ...] = ()
    conflicts: tuple[MergeConflict, ...] = ()
    resolutions: tuple[MergeResolution, ...] = ()

    def count(self, kind: MergeItemKind) -> int:
        """Count newly added direct items of one kind."""

        return sum(addition.kind is kind for addition in self.additions)


class MergePort(Protocol):
    """Freeze and atomically apply one authorized structural Merge."""

    def freeze(self, request: MergeRequest) -> FrozenMergePlan:
        """Resolve and plan one Merge without changing durable state."""

    def apply(
        self,
        plan: FrozenMergePlan,
        resolutions: tuple[MergeResolution, ...],
    ) -> MergeResult:
        """Commit the frozen plan or publish none of it."""


def resolve_merge_conflicts(
    plan: FrozenMergePlan,
    *,
    resolutions: tuple[MergeResolution, ...] = (),
    bulk: MergeDecision | None = None,
) -> tuple[MergeResolution, ...]:
    """Return one exact, complete, conflict-ordered decision set."""

    if not isinstance(plan, FrozenMergePlan):
        raise TypeError("Merge conflict resolution requires a frozen plan.")
    if bulk is not None and not isinstance(bulk, MergeDecision):
        raise TypeError("Merge bulk decision is invalid.")
    if bulk is not None and resolutions:
        raise MergeError("Use either one Merge bulk decision or per-item resolutions.")
    if any(not isinstance(value, MergeResolution) for value in resolutions):
        raise TypeError("Merge resolutions must be MergeResolution values.")
    conflicts = {conflict.uid: conflict for conflict in plan.conflicts}
    if bulk is not None:
        unavailable = [
            conflict.uid
            for conflict in plan.conflicts
            if bulk not in conflict.allowed_decisions
        ]
        if unavailable:
            raise MergeError(
                f"Merge bulk decision {bulk.value} is not authorized for: "
                + ", ".join(unavailable)
            )
        return tuple(
            MergeResolution(conflict_uid=conflict.uid, decision=bulk)
            for conflict in plan.conflicts
        )
    supplied: dict[str, MergeDecision] = {}
    for resolution in resolutions:
        if resolution.conflict_uid not in conflicts:
            raise MergeError(
                f"Merge resolution names an unknown conflict: "
                f"'{resolution.conflict_uid}'."
            )
        previous = supplied.get(resolution.conflict_uid)
        if previous is not None:
            raise MergeError(
                f"Merge resolution repeats conflict '{resolution.conflict_uid}'."
            )
        supplied[resolution.conflict_uid] = resolution.decision
        if resolution.decision not in conflicts[
            resolution.conflict_uid
        ].allowed_decisions:
            raise MergeError(
                f"Merge decision {resolution.decision.value} is not authorized "
                f"for conflict '{resolution.conflict_uid}'."
            )
    missing = [
        conflict.uid for conflict in plan.conflicts if conflict.uid not in supplied
    ]
    if missing:
        raise MergeError(
            "Merge has unresolved required conflicts: " + ", ".join(missing)
        )
    return tuple(
        MergeResolution(
            conflict_uid=conflict.uid,
            decision=supplied[conflict.uid],
        )
        for conflict in plan.conflicts
    )


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
    if type(plan.mutates_granted_authority) is not bool:
        raise MergeError("Merge plan has invalid Target authority metadata.")
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
    if (
        tuple(item for context in plan.contexts for item in context.unchanged)
        != plan.unchanged
    ):
        raise MergeError("Merge plan unchanged items do not cover its Context pairs.")
    if (
        tuple(item for context in plan.contexts for item in context.conflicts)
        != plan.conflicts
    ):
        raise MergeError("Merge plan conflicts do not cover its Context pairs.")
    conflict_uids = tuple(conflict.uid for conflict in plan.conflicts)
    if len(conflict_uids) != len(set(conflict_uids)):
        raise MergeError("Merge plan repeats a mapping-qualified conflict identity.")
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
    resolutions: tuple[MergeResolution, ...] = (),
    bulk: MergeDecision | None = None,
) -> MergeResult:
    """Apply one structural Merge without CLI, TUI, or provider dependencies."""

    validated = validate_merge_request(request)
    plan = frozen_plan or prepare_merge(validated, port=port)
    if not isinstance(plan, FrozenMergePlan):
        raise TypeError("Merge requires a valid frozen plan.")
    if plan.request != validated:
        raise MergeError("The frozen Merge plan no longer matches the request.")
    resolved = resolve_merge_conflicts(
        plan,
        resolutions=resolutions,
        bulk=bulk,
    )
    result = port.apply(plan, resolved)
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
        or result.unchanged != plan.unchanged
        or result.conflicts != plan.conflicts
        or result.resolutions != resolved
        or not result.checkpoint_uid
        or not result.checkpoint_uids
        or result.checkpoint_uid != result.checkpoint_uids[0]
        or len(result.checkpoint_uids) != len(result.contexts)
        or len(set(result.checkpoint_uids)) != len(result.checkpoint_uids)
    ):
        raise MergeError("Merge receipt does not match the frozen plan.")
    return result
