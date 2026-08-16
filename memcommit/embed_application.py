"""Terminal-independent application contract for embedding one Context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class EmbedError(RuntimeError):
    """Raised when one Embed request cannot be completed atomically."""


@dataclass(frozen=True)
class EmbedPlacement:
    """One exact gap in a frozen target direct-item order."""

    position: int
    previous_uid: str | None
    next_uid: str | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
        ):
            raise ValueError("Embed placement requires a nonnegative position.")
        if self.position == 0 and self.previous_uid is not None:
            raise ValueError("The first Embed gap cannot have a previous item.")


@dataclass(frozen=True)
class EmbedRequest:
    """One stable Embed request independent of argv and terminal state."""

    child_locator: str
    into_locator: str
    before: str | None = None
    after: str | None = None


@dataclass(frozen=True)
class FrozenEmbedPlan:
    """Reviewed identities and insertion gap plus an opaque Store binding."""

    request: EmbedRequest
    child_name: str
    child_uid: str
    child_digest: str
    into_name: str
    into_uid: str
    into_digest: str
    placement: EmbedPlacement
    item_count: int
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class EmbedResult:
    """Typed durable receipt shared by CLI, TUI, and future Python adapters."""

    child_name: str
    child_uid: str
    into_name: str
    into_uid: str
    placement: EmbedPlacement
    checkpoint_uid: str


# Explicit aliases name the existing closed route without breaking callers
# while Memory Embed is added beside it.
ContextEmbedRequest = EmbedRequest
FrozenContextEmbedPlan = FrozenEmbedPlan
ContextEmbedResult = EmbedResult


@dataclass(frozen=True)
class MemoryEmbedRequest:
    """One live Source Memory link and exact local Target placement."""

    memory_selector: str
    source_locator: str
    into_locator: str
    before: str | None = None
    after: str | None = None


@dataclass(frozen=True)
class FrozenMemoryEmbedPlan:
    """Reviewed live-link identities and exact Target insertion gap."""

    request: MemoryEmbedRequest
    source_name: str
    source_uid: str
    source_digest: str
    memory_uid: str
    memory_content: str
    memory_content_sha256: str
    into_name: str
    into_uid: str
    into_digest: str
    placement: EmbedPlacement
    item_count: int
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class MemoryEmbedResult:
    """Durable live Memory Embed receipt shared by every adapter."""

    embed_uid: str
    source_name: str
    source_uid: str
    memory_uid: str
    into_name: str
    into_uid: str
    placement: EmbedPlacement
    checkpoint_uid: str


class EmbedPort(Protocol):
    """Freeze and atomically apply one authorized Context relationship."""

    def freeze(self, request: EmbedRequest) -> FrozenEmbedPlan:
        """Resolve and freeze one request without changing durable state."""

    def apply(self, plan: FrozenEmbedPlan) -> EmbedResult:
        """Commit the frozen plan or publish none of it."""


class MemoryEmbedPort(Protocol):
    """Freeze and atomically apply one local live Memory relationship."""

    def freeze_memory(self, request: MemoryEmbedRequest) -> FrozenMemoryEmbedPlan:
        """Resolve one direct Source Memory and exact Target gap."""

    def apply_memory(self, plan: FrozenMemoryEmbedPlan) -> MemoryEmbedResult:
        """Commit the frozen live link or publish none of it."""


def validate_embed_request(request: EmbedRequest) -> EmbedRequest:
    """Validate adapter-independent request shape before opening a Store."""

    if not isinstance(request, EmbedRequest):
        raise TypeError("Embed requires an EmbedRequest.")
    for value, label in (
        (request.child_locator, "Child locator"),
        (request.into_locator, "Into locator"),
    ):
        if not isinstance(value, str) or not value:
            raise EmbedError(f"Embed {label} must be nonempty text.")
    if request.before is not None and (
        not isinstance(request.before, str) or not request.before
    ):
        raise EmbedError("Embed before selector must be nonempty text.")
    if request.after is not None and (
        not isinstance(request.after, str) or not request.after
    ):
        raise EmbedError("Embed after selector must be nonempty text.")
    if request.before is not None and request.after is not None:
        raise EmbedError("Pass only one of --before or --after.")
    return request


def validate_memory_embed_request(
    request: MemoryEmbedRequest,
) -> MemoryEmbedRequest:
    """Validate one adapter-independent live Memory Embed request."""

    if not isinstance(request, MemoryEmbedRequest):
        raise TypeError("Memory Embed requires a MemoryEmbedRequest.")
    for value, label in (
        (request.memory_selector, "Memory selector"),
        (request.source_locator, "Source locator"),
        (request.into_locator, "Into locator"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise EmbedError(f"Memory Embed {label} must be nonempty text.")
    for value, label in ((request.before, "before"), (request.after, "after")):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise EmbedError(f"Memory Embed {label} selector must be nonempty text.")
    if request.before is not None and request.after is not None:
        raise EmbedError("Pass only one of --before or --after.")
    return request


def prepare_embed(
    request: EmbedRequest,
    *,
    port: EmbedPort,
) -> FrozenEmbedPlan:
    """Freeze one canonical, reviewable Embed plan without mutation."""

    validated = validate_embed_request(request)
    plan = port.freeze(validated)
    if not isinstance(plan, FrozenEmbedPlan):
        raise TypeError("Embed port returned an invalid frozen plan.")
    if plan.request != validated:
        raise EmbedError("Embed plan does not describe the requested operation.")
    if not all(
        (
            plan.child_name,
            plan.child_uid,
            plan.child_digest,
            plan.into_name,
            plan.into_uid,
            plan.into_digest,
        )
    ):
        raise EmbedError("Embed plan has an incomplete Context binding.")
    if not 0 <= plan.placement.position <= plan.item_count:
        raise EmbedError("Embed plan has an invalid insertion gap.")
    return plan


def run_embed(
    request: EmbedRequest,
    *,
    port: EmbedPort,
    frozen_plan: FrozenEmbedPlan | None = None,
) -> EmbedResult:
    """Apply one reviewed Embed without CLI, TUI, or provider dependencies."""

    validated = validate_embed_request(request)
    plan = frozen_plan or prepare_embed(validated, port=port)
    if not isinstance(plan, FrozenEmbedPlan):
        raise TypeError("Embed requires a valid frozen plan.")
    if plan.request != validated:
        raise EmbedError("The frozen Embed plan no longer matches the request.")
    result = port.apply(plan)
    if not isinstance(result, EmbedResult):
        raise TypeError("Embed port returned an invalid durable receipt.")
    if (
        result.child_name != plan.child_name
        or result.child_uid != plan.child_uid
        or result.into_name != plan.into_name
        or result.into_uid != plan.into_uid
        or result.placement != plan.placement
        or not result.checkpoint_uid
    ):
        raise EmbedError("Embed receipt does not match the frozen plan.")
    return result


def prepare_memory_embed(
    request: MemoryEmbedRequest,
    *,
    port: MemoryEmbedPort,
) -> FrozenMemoryEmbedPlan:
    """Freeze one exact live Memory link without mutation."""

    validated = validate_memory_embed_request(request)
    plan = port.freeze_memory(validated)
    if not isinstance(plan, FrozenMemoryEmbedPlan):
        raise TypeError("Memory Embed port returned an invalid frozen plan.")
    if plan.request != validated:
        raise EmbedError("Memory Embed plan does not describe the request.")
    if not all(
        (
            plan.source_name,
            plan.source_uid,
            plan.source_digest,
            plan.memory_uid,
            plan.memory_content_sha256,
            plan.into_name,
            plan.into_uid,
            plan.into_digest,
        )
    ):
        raise EmbedError("Memory Embed plan has an incomplete binding.")
    if not 0 <= plan.placement.position <= plan.item_count:
        raise EmbedError("Memory Embed plan has an invalid insertion gap.")
    return plan


def run_memory_embed(
    request: MemoryEmbedRequest,
    *,
    port: MemoryEmbedPort,
    frozen_plan: FrozenMemoryEmbedPlan | None = None,
) -> MemoryEmbedResult:
    """Apply one reviewed live Memory link through the supplied port."""

    validated = validate_memory_embed_request(request)
    plan = frozen_plan or prepare_memory_embed(validated, port=port)
    if not isinstance(plan, FrozenMemoryEmbedPlan):
        raise TypeError("Memory Embed requires a valid frozen plan.")
    if plan.request != validated:
        raise EmbedError("Frozen Memory Embed plan no longer matches the request.")
    result = port.apply_memory(plan)
    if not isinstance(result, MemoryEmbedResult):
        raise TypeError("Memory Embed port returned an invalid durable receipt.")
    if (
        result.source_name != plan.source_name
        or result.source_uid != plan.source_uid
        or result.memory_uid != plan.memory_uid
        or result.into_name != plan.into_name
        or result.into_uid != plan.into_uid
        or result.placement != plan.placement
        or not result.embed_uid
        or not result.checkpoint_uid
    ):
        raise EmbedError("Memory Embed receipt does not match the frozen plan.")
    return result


__all__ = [
    "ContextEmbedRequest",
    "ContextEmbedResult",
    "EmbedError",
    "EmbedPlacement",
    "EmbedPort",
    "EmbedRequest",
    "EmbedResult",
    "FrozenContextEmbedPlan",
    "FrozenEmbedPlan",
    "FrozenMemoryEmbedPlan",
    "MemoryEmbedPort",
    "MemoryEmbedRequest",
    "MemoryEmbedResult",
    "prepare_embed",
    "prepare_memory_embed",
    "run_embed",
    "run_memory_embed",
    "validate_embed_request",
    "validate_memory_embed_request",
]
