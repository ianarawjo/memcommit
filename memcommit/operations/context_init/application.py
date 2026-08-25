"""Terminal-independent application boundary for ordinary Context initialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import uuid


class ContextInitError(RuntimeError):
    """An ordinary Context initialization could not reach its exact outcome."""


@dataclass(frozen=True)
class ContextInitRequest:
    """One exact initialization request independent of argv and terminal state."""

    name: str
    create_parents: bool
    expected_current: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ContextInitError("A new Context name is required.")
        if type(self.create_parents) is not bool:
            raise ContextInitError("Context parent creation mode is invalid.")
        if self.expected_current is not None and (
            not isinstance(self.expected_current, str)
            or not self.expected_current.strip()
        ):
            raise ContextInitError("Expected current Context is invalid.")


@dataclass(frozen=True)
class ContextInitEntry:
    """One planned Context and its operation-owned checkpoint description."""

    name: str
    requested_name: str
    create_parents: bool
    is_leaf: bool

    @property
    def checkpoint_args(self) -> dict[str, object]:
        if not self.create_parents:
            return {"name": self.name}
        return {
            "name": self.name,
            "parents": True,
            "requested_name": self.requested_name,
        }

    @property
    def checkpoint_description(self) -> str:
        if self.is_leaf:
            return f"Initialized context '{self.name}'"
        return (
            f"Initialized namespace parent '{self.name}' "
            f"for '{self.requested_name}'"
        )


@dataclass(frozen=True)
class ContextInitPlan:
    """Complete require-new/reuse and current-switch policy for one request."""

    request: ContextInitRequest
    entries: tuple[ContextInitEntry, ...]
    require_all_new: bool


@dataclass(frozen=True)
class CreatedContext:
    """Stable identity of one Context created by the initialization batch."""

    name: str
    uid: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ContextInitError("Created Context name is invalid.")
        try:
            canonical_uid = str(uuid.UUID(self.uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ContextInitError("Created Context identity is invalid.") from error
        if canonical_uid != self.uid:
            raise ContextInitError("Created Context identity is invalid.")


@dataclass(frozen=True)
class ContextInitResult:
    """Typed creation receipt shared by console and future public adapters."""

    requested_name: str
    create_parents: bool
    created: tuple[CreatedContext, ...]
    reused_names: tuple[str, ...]
    current_name: str

    @property
    def created_names(self) -> tuple[str, ...]:
        return tuple(context.name for context in self.created)


class ContextInitPort(Protocol):
    """Validate and atomically publish one planned Context namespace batch."""

    def apply(self, plan: ContextInitPlan) -> tuple[CreatedContext, ...]:
        """Create the missing entries and CAS-select the exact requested leaf."""


def plan_context_init(request: ContextInitRequest) -> ContextInitPlan:
    """Expand one exact name into the operation-owned creation/checkpoint plan."""

    if request.create_parents:
        parts = request.name.split("/")
        names = tuple(
            "/".join(parts[:index]) for index in range(1, len(parts) + 1)
        )
    else:
        names = (request.name,)
    entries = tuple(
        ContextInitEntry(
            name=name,
            requested_name=request.name,
            create_parents=request.create_parents,
            is_leaf=name == request.name,
        )
        for name in names
    )
    return ContextInitPlan(
        request=request,
        entries=entries,
        require_all_new=not request.create_parents,
    )


def run_context_init(
    request: ContextInitRequest,
    *,
    port: ContextInitPort,
) -> ContextInitResult:
    """Create and select one ordinary Context without CLI or TUI dependencies."""

    plan = plan_context_init(request)
    created = port.apply(plan)
    created_names = tuple(context.name for context in created)
    planned_names = tuple(entry.name for entry in plan.entries)
    created_name_set = set(created_names)
    if (
        len(set(created_names)) != len(created_names)
        or any(name not in planned_names for name in created_names)
        or tuple(name for name in planned_names if name in created_name_set)
        != created_names
        or (plan.require_all_new and created_names != planned_names)
    ):
        raise ContextInitError(
            "Context initialization returned a receipt outside its creation plan."
        )
    reused_names = tuple(name for name in planned_names if name not in created_names)
    return ContextInitResult(
        requested_name=request.name,
        create_parents=request.create_parents,
        created=created,
        reused_names=reused_names,
        current_name=request.name,
    )
