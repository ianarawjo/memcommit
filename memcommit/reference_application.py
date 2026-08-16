"""Terminal-independent application contract for one Memory snapshot Reference."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ReferenceError(RuntimeError):
    """Raised when a snapshot Reference cannot be published exactly."""


@dataclass(frozen=True)
class ReferenceRequest:
    """One Source Memory and local Target independent of argv or terminal state."""

    memory_selector: str
    source_locator: str
    into_locator: str | None = None


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


class ReferencePort(Protocol):
    """Freeze and atomically publish one local snapshot Reference."""

    def freeze(self, request: ReferenceRequest) -> FrozenReferencePlan:
        """Resolve exact Source content and Target revision without mutation."""

    def apply(self, plan: FrozenReferencePlan) -> ReferenceResult:
        """Publish the frozen snapshot or none of it."""


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


__all__ = [
    "FrozenReferencePlan",
    "ReferenceError",
    "ReferencePort",
    "ReferenceRequest",
    "ReferenceResult",
    "prepare_reference",
    "run_reference",
    "validate_reference_request",
]
