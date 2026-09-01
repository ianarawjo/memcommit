"""Terminal-independent application contract for adding Memories."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Literal, Protocol


AddInputMode = Literal[
    "SINGLE",
    "EXPLICIT_BATCH",
    "PASTE",
    "TUI_DRAFTS",
]


class AddError(RuntimeError):
    """Raised when one Add request cannot be completed atomically."""


@dataclass(frozen=True)
class AddSource:
    """Exact intake provenance retained with the Add checkpoint."""

    mode: AddInputMode
    kind: str
    parser: str
    raw_text: str

    def __post_init__(self) -> None:
        if self.mode not in {
            "SINGLE",
            "EXPLICIT_BATCH",
            "PASTE",
            "TUI_DRAFTS",
        }:
            raise ValueError("Add source mode is invalid.")
        for value, label in (
            (self.kind, "kind"),
            (self.parser, "parser"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Add source {label} must be nonempty text.")
        if not isinstance(self.raw_text, str):
            raise TypeError("Add source raw text must be text.")


@dataclass(frozen=True)
class AddRequest:
    """One stable Add request independent of argv and terminal state."""

    contents: tuple[str, ...]
    source: AddSource
    context_locator: str | None = None


@dataclass(frozen=True)
class AddedMemory:
    """One durable Memory created by Add."""

    uid: str
    content: str


@dataclass(frozen=True)
class AddResult:
    """Typed durable Add receipt shared by public adapters."""

    context_name: str
    context_uid: str
    memories: tuple[AddedMemory, ...]
    checkpoint_uid: str

    @property
    def count(self) -> int:
        return len(self.memories)


@dataclass(frozen=True)
class FrozenAddTarget:
    """Reviewed target identity plus an opaque infrastructure binding."""

    context_name: str
    context_uid: str
    token: object = field(repr=False, compare=False)


class AddTargetPort(Protocol):
    """Append validated Memories through one authorized durable boundary."""

    def freeze(self, context_locator: str | None) -> FrozenAddTarget:
        """Resolve one authorized target identity for review and commit."""

    def append(
        self,
        target: FrozenAddTarget,
        request: AddRequest,
    ) -> AddResult:
        """Commit all requested Memories or publish none of them."""


def validate_add_request(request: AddRequest) -> AddRequest:
    """Validate the complete batch before any target or Store is opened."""

    if not isinstance(request, AddRequest):
        raise TypeError("Add requires an AddRequest.")
    if not request.contents:
        raise AddError("Add requires at least one Memory.")
    if any(not isinstance(content, str) for content in request.contents):
        raise AddError("Every Add Memory must be text.")
    if any(not content.strip() for content in request.contents):
        raise AddError("Every Add Memory must contain nonblank text.")
    if request.source.mode == "SINGLE" and len(request.contents) != 1:
        raise AddError("Single Add source must contain exactly one Memory.")
    if request.context_locator is not None and (
        not isinstance(request.context_locator, str) or not request.context_locator
    ):
        raise AddError("Add Context locator must be nonempty text.")
    return request


def prepare_add_target(
    context_locator: str | None,
    *,
    target_port: AddTargetPort,
) -> FrozenAddTarget:
    """Freeze one reviewed Add target without changing it."""

    if context_locator is not None and (
        not isinstance(context_locator, str) or not context_locator
    ):
        raise AddError("Add Context locator must be nonempty text.")
    target = target_port.freeze(context_locator)
    if not isinstance(target, FrozenAddTarget):
        raise TypeError("Add target port returned an invalid frozen target.")
    if not target.context_name or not target.context_uid:
        raise AddError("Add target binding is incomplete.")
    return target


def run_add(
    request: AddRequest,
    *,
    target_port: AddTargetPort,
    frozen_target: FrozenAddTarget | None = None,
) -> AddResult:
    """Add one validated batch without CLI, TUI, or provider dependencies."""

    validated = validate_add_request(request)
    target = frozen_target or prepare_add_target(
        validated.context_locator,
        target_port=target_port,
    )
    if not isinstance(target, FrozenAddTarget):
        raise TypeError("Add requires a valid frozen target.")
    result = target_port.append(target, validated)
    if not isinstance(result, AddResult):
        raise TypeError("Add target returned an invalid result.")
    if result.count != len(validated.contents):
        raise AddError("Add target returned an incomplete durable receipt.")
    if tuple(memory.content for memory in result.memories) != validated.contents:
        raise AddError("Add target receipt does not match the requested Memories.")
    if (
        result.context_name != target.context_name
        or result.context_uid != target.context_uid
    ):
        raise AddError("Add target receipt does not match the frozen target.")
    return result
