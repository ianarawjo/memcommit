"""Terminal-independent contracts for immutable Memory or Context References."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ReferenceError(RuntimeError):
    """Raised when a snapshot Reference cannot be published exactly."""


# A retained snapshot survives Grant revocation. The current Context-use model
# treats READ as the enforceable disclosure boundary for locally owned output.
# Keep the operation-owned tuple explicit so every adapter uses the same check.
GRANTED_MEMORY_REFERENCE_PERMISSIONS = (
    "READ",
)


@dataclass(frozen=True)
class ReferenceRequest:
    """One Source Memory and local Target independent of argv or terminal state."""

    memory_selector: str
    source_locator: str
    into_locator: str | None = None


# Keep the original public type stable while making the unit explicit beside
# the new Context route.
MemoryReferenceRequest = ReferenceRequest


@dataclass(frozen=True)
class ContextReferenceRequest:
    """One local or READ-granted Context scope and exact local Target."""

    source_locator: str
    into_locator: str | None = None
    include_descendants: bool = False
    follow_embeds: bool = False

    def __post_init__(self) -> None:
        if self.include_descendants != self.follow_embeds:
            raise ReferenceError(
                "Context Reference scope must be direct or fully recursive."
            )


@dataclass(frozen=True)
class FrozenReferencePlan:
    """Exact Source content and Target revision reviewed for publication."""

    request: ReferenceRequest
    source_name: str
    source_uid: str
    source_digest: str
    memory_uid: str
    memory_content: str
    memory_content_sha256: str
    into_name: str
    into_uid: str
    into_digest: str
    token: object = field(repr=False, compare=False)


FrozenMemoryReferencePlan = FrozenReferencePlan


@dataclass(frozen=True)
class FrozenContextReferencePlan:
    """Exact self-contained Context package and Target revision under review."""

    request: ContextReferenceRequest
    source_name: str
    source_uid: str
    source_bindings: tuple[tuple[str, str, str], ...]
    snapshot_package: dict[str, object] = field(repr=False, compare=True)
    snapshot_content_sha256: str
    into_name: str
    into_uid: str
    into_digest: str
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class ReferenceResult:
    """Durable snapshot receipt shared by every adapter."""

    reference_uid: str
    source_name: str
    source_uid: str
    memory_uid: str
    memory_content_sha256: str
    into_name: str
    into_uid: str
    checkpoint_uid: str


MemoryReferenceResult = ReferenceResult


@dataclass(frozen=True)
class ContextReferenceResult:
    """Durable receipt for one immutable Context snapshot."""

    reference_uid: str
    source_name: str
    source_uid: str
    snapshot_content_sha256: str
    include_descendants: bool
    follow_embeds: bool
    context_count: int
    into_name: str
    into_uid: str
    checkpoint_uid: str


class ReferencePort(Protocol):
    """Freeze and atomically publish one snapshot into a local Target."""

    def freeze(self, request: ReferenceRequest) -> FrozenReferencePlan:
        """Resolve exact Source content and Target revision without mutation."""

    def apply(self, plan: FrozenReferencePlan) -> ReferenceResult:
        """Publish the frozen snapshot or none of it."""

    def freeze_context(
        self,
        request: ContextReferenceRequest,
    ) -> FrozenContextReferencePlan:
        """Freeze one exact local or READ-granted package without mutation."""

    def apply_context(
        self,
        plan: FrozenContextReferencePlan,
    ) -> ContextReferenceResult:
        """Publish the frozen Context snapshot or none of it."""


def validate_reference_request(request: ReferenceRequest) -> ReferenceRequest:
    """Validate adapter-independent Reference input shape."""

    if not isinstance(request, ReferenceRequest):
        raise TypeError("Reference requires a ReferenceRequest.")
    for value, label in (
        (request.memory_selector, "Memory selector"),
        (request.source_locator, "Source locator"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ReferenceError(f"Reference {label} must be nonempty text.")
    if request.into_locator is not None and (
        not isinstance(request.into_locator, str) or not request.into_locator.strip()
    ):
        raise ReferenceError("Reference Target locator must be nonempty text.")
    return request


def validate_context_reference_request(
    request: ContextReferenceRequest,
) -> ContextReferenceRequest:
    """Validate one adapter-independent Context Reference request."""

    if not isinstance(request, ContextReferenceRequest):
        raise TypeError("Context Reference requires a ContextReferenceRequest.")
    if (
        not isinstance(request.source_locator, str)
        or not request.source_locator.strip()
    ):
        raise ReferenceError(
            "Context Reference Source locator must be nonempty text."
        )
    for value, label in ((request.into_locator, "Target locator"),):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ReferenceError(
                f"Context Reference {label} must be nonempty text."
            )
    if type(request.include_descendants) is not bool:
        raise ReferenceError("Context Reference descendant scope must be boolean.")
    if type(request.follow_embeds) is not bool:
        raise ReferenceError("Context Reference Embed reach must be boolean.")
    if request.include_descendants != request.follow_embeds:
        raise ReferenceError(
            "Context Reference scope must be direct or fully recursive."
        )
    return request


def prepare_reference(
    request: ReferenceRequest,
    *,
    port: ReferencePort,
) -> FrozenReferencePlan:
    """Freeze one exact Source Memory snapshot and Target revision."""

    validated = validate_reference_request(request)
    plan = port.freeze(validated)
    if not isinstance(plan, FrozenReferencePlan):
        raise TypeError("Reference port returned an invalid frozen plan.")
    if plan.request != validated:
        raise ReferenceError("Reference plan does not describe the request.")
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
        raise ReferenceError("Reference plan has an incomplete binding.")
    return plan


def run_reference(
    request: ReferenceRequest,
    *,
    port: ReferencePort,
    frozen_plan: FrozenReferencePlan | None = None,
) -> ReferenceResult:
    """Publish one exact snapshot through the supplied infrastructure port."""

    validated = validate_reference_request(request)
    plan = frozen_plan or prepare_reference(validated, port=port)
    if not isinstance(plan, FrozenReferencePlan):
        raise TypeError("Reference requires a valid frozen plan.")
    if plan.request != validated:
        raise ReferenceError("Frozen Reference plan no longer matches the request.")
    result = port.apply(plan)
    if not isinstance(result, ReferenceResult):
        raise TypeError("Reference port returned an invalid durable receipt.")
    if (
        result.source_name != plan.source_name
        or result.source_uid != plan.source_uid
        or result.memory_uid != plan.memory_uid
        or result.memory_content_sha256 != plan.memory_content_sha256
        or result.into_name != plan.into_name
        or result.into_uid != plan.into_uid
        or not result.reference_uid
        or not result.checkpoint_uid
    ):
        raise ReferenceError("Reference receipt does not match the frozen plan.")
    return result


def prepare_context_reference(
    request: ContextReferenceRequest,
    *,
    port: ReferencePort,
) -> FrozenContextReferencePlan:
    """Freeze one complete direct or recursive Context snapshot."""

    validated = validate_context_reference_request(request)
    plan = port.freeze_context(validated)
    if not isinstance(plan, FrozenContextReferencePlan):
        raise TypeError("Reference port returned an invalid Context plan.")
    if plan.request != validated:
        raise ReferenceError("Context Reference plan does not describe the request.")
    if not all(
        (
            plan.source_name,
            plan.source_uid,
            plan.source_bindings,
            plan.snapshot_package,
            plan.snapshot_content_sha256,
            plan.into_name,
            plan.into_uid,
            plan.into_digest,
        )
    ):
        raise ReferenceError("Context Reference plan has an incomplete binding.")
    return plan


def run_context_reference(
    request: ContextReferenceRequest,
    *,
    port: ReferencePort,
    frozen_plan: FrozenContextReferencePlan | None = None,
) -> ContextReferenceResult:
    """Publish one exact immutable Context snapshot."""

    validated = validate_context_reference_request(request)
    plan = frozen_plan or prepare_context_reference(validated, port=port)
    if not isinstance(plan, FrozenContextReferencePlan):
        raise TypeError("Context Reference requires a valid frozen plan.")
    if plan.request != validated:
        raise ReferenceError(
            "Frozen Context Reference plan no longer matches the request."
        )
    result = port.apply_context(plan)
    if not isinstance(result, ContextReferenceResult):
        raise TypeError("Reference port returned an invalid Context receipt.")
    if (
        result.source_name != plan.source_name
        or result.source_uid != plan.source_uid
        or result.snapshot_content_sha256 != plan.snapshot_content_sha256
        or result.include_descendants != plan.request.include_descendants
        or result.follow_embeds != plan.request.follow_embeds
        or result.context_count != len(plan.snapshot_package["contexts"])
        or result.into_name != plan.into_name
        or result.into_uid != plan.into_uid
        or not result.reference_uid
        or not result.checkpoint_uid
    ):
        raise ReferenceError("Context Reference receipt does not match the frozen plan.")
    return result


__all__ = [
    "ContextReferenceRequest",
    "ContextReferenceResult",
    "FrozenContextReferencePlan",
    "FrozenMemoryReferencePlan",
    "FrozenReferencePlan",
    "GRANTED_MEMORY_REFERENCE_PERMISSIONS",
    "MemoryReferenceRequest",
    "MemoryReferenceResult",
    "ReferenceError",
    "ReferencePort",
    "ReferenceRequest",
    "ReferenceResult",
    "prepare_context_reference",
    "prepare_reference",
    "run_context_reference",
    "run_reference",
    "validate_context_reference_request",
    "validate_reference_request",
]
