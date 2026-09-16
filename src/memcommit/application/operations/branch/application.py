"""Terminal-independent application contract for branching Contexts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names


class BranchError(RuntimeError):
    """One exact or lexical-subtree Branch could not be completed."""


@dataclass(frozen=True, slots=True)
class BranchRequest:
    """One canonical Branch request against a command-start local catalog."""

    source_name: str
    target_name: str
    include_descendants: bool
    expected_current: str | None
    local_context_names: tuple[str, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.source_name, "Source Context"),
            (self.target_name, "Target Context"),
        ):
            if (
                not isinstance(value, str)
                or not value
                or "\n" in value
                or "\r" in value
            ):
                raise BranchError(f"Branch {label} must be one exact name.")
        if type(self.include_descendants) is not bool:
            raise BranchError("Branch descendant scope is invalid.")
        if self.expected_current is not None and (
            not isinstance(self.expected_current, str)
            or not self.expected_current
        ):
            raise BranchError("Branch expected current Context is invalid.")
        if (
            not isinstance(self.local_context_names, tuple)
            or len(set(self.local_context_names)) != len(self.local_context_names)
            or any(
                not isinstance(name, str) or not name
                for name in self.local_context_names
            )
        ):
            raise BranchError("Branch requires one frozen local Context catalog.")
        if self.source_name not in self.local_context_names:
            raise BranchError(
                f"Branch Source '{self.source_name}' is not in the frozen "
                "local catalog."
            )


@dataclass(frozen=True, slots=True)
class BranchContextPlan:
    """One exact Source-to-target Context mapping in a Branch publication."""

    source_name: str
    target_name: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.source_name, self.target_name)
        ):
            raise BranchError("A Branch Context mapping is incomplete.")


@dataclass(frozen=True, slots=True)
class BranchPlan:
    """Complete Source membership and require-new target mapping."""

    request: BranchRequest
    contexts: tuple[BranchContextPlan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.contexts, tuple) or not self.contexts:
            raise BranchError("A Branch plan requires its Source root.")
        pairs = tuple(
            (context.source_name, context.target_name)
            for context in self.contexts
        )
        if (
            pairs[0]
            != (self.request.source_name, self.request.target_name)
            or len({source for source, _target in pairs}) != len(pairs)
            or len({target for _source, target in pairs}) != len(pairs)
            or (not self.request.include_descendants and len(pairs) != 1)
        ):
            raise BranchError("A Branch plan contains an invalid Context mapping.")

    @property
    def context_count(self) -> int:
        return len(self.contexts)

    @property
    def descendant_count(self) -> int:
        return max(0, self.context_count - 1)


@dataclass(frozen=True, slots=True)
class BranchedContext:
    """Stable Source and target identities published for one mapping."""

    source_name: str
    source_uid: str
    target_name: str
    target_uid: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.source_name,
                self.source_uid,
                self.target_name,
                self.target_uid,
            )
        ):
            raise BranchError("A published Branch Context identity is incomplete.")


@dataclass(frozen=True, slots=True)
class BranchResult:
    """Typed publication receipt independent of console presentation."""

    source_root: str
    target_root: str
    include_descendants: bool
    contexts: tuple[BranchedContext, ...]
    current_context_name: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_root, str)
            or not self.source_root
            or not isinstance(self.target_root, str)
            or not self.target_root
            or type(self.include_descendants) is not bool
            or not isinstance(self.contexts, tuple)
            or not self.contexts
            or not isinstance(self.current_context_name, str)
            or not self.current_context_name
        ):
            raise BranchError("A Branch publication receipt is incomplete.")
        if (
            len({context.source_name for context in self.contexts})
            != len(self.contexts)
            or len({context.target_name for context in self.contexts})
            != len(self.contexts)
        ):
            raise BranchError("A Branch publication receipt contains duplicates.")

    @property
    def context_count(self) -> int:
        return len(self.contexts)

    @property
    def descendant_count(self) -> int:
        return max(0, self.context_count - 1)


class BranchPort(Protocol):
    """Materialize one planned Branch through an atomic infrastructure port."""

    def apply(self, plan: BranchPlan) -> BranchResult:
        """Publish every mapped target and select the target root."""


def plan_branch(request: BranchRequest) -> BranchPlan:
    """Freeze lexical Source membership and its require-new name mapping."""

    try:
        validate_portable_context_name(request.target_name)
    except ValueError as error:
        raise BranchError(str(error)) from error

    source_names = expand_lexical_context_names(
        ContextScope.create(
            (request.source_name,),
            include_descendants=request.include_descendants,
        ),
        request.local_context_names,
    )
    contexts = tuple(
        BranchContextPlan(
            source_name=source_name,
            target_name=(
                request.target_name
                + source_name[len(request.source_name) :]
            ),
        )
        for source_name in source_names
    )
    if not contexts or contexts[0].source_name != request.source_name:
        raise BranchError("Branch planning lost its exact Source root.")
    if not request.include_descendants and len(contexts) != 1:
        raise BranchError("An exact Branch may contain only its Source root.")
    if len({context.target_name for context in contexts}) != len(contexts):
        raise BranchError("Branch target mapping contains duplicate Context names.")

    occupied = next(
        (
            context.target_name
            for context in contexts
            if context.target_name in request.local_context_names
        ),
        None,
    )
    if occupied is not None:
        raise BranchError(f"Context '{occupied}' already exists.")
    return BranchPlan(request=request, contexts=contexts)


def run_branch(
    request: BranchRequest,
    *,
    port: BranchPort,
) -> BranchResult:
    """Plan and atomically publish one Branch without terminal dependencies."""

    plan = plan_branch(request)
    result = port.apply(plan)
    expected_pairs = tuple(
        (context.source_name, context.target_name) for context in plan.contexts
    )
    published_pairs = tuple(
        (context.source_name, context.target_name) for context in result.contexts
    )
    if (
        result.source_root != request.source_name
        or result.target_root != request.target_name
        or result.include_descendants != request.include_descendants
        or result.current_context_name != request.target_name
        or published_pairs != expected_pairs
    ):
        raise BranchError("Branch publication returned a receipt outside its plan.")
    return result


__all__ = [
    "BranchContextPlan",
    "BranchError",
    "BranchPlan",
    "BranchPort",
    "BranchRequest",
    "BranchResult",
    "BranchedContext",
    "plan_branch",
    "run_branch",
]
