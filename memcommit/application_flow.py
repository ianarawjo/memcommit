"""Operation-neutral review-to-application phase orchestration.

The flow deliberately owns only phase order. Operation adapters retain the
meaning of review, freshness, authority, CAS, rollback, checkpoints, receipts,
and recovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar


PreparedT = TypeVar("PreparedT")
AppliedT = TypeVar("AppliedT")
ApplicationFlowStatus = Literal["CANCELLED", "APPLIED"]


class ApplicationFlowPort(Protocol[PreparedT, AppliedT]):
    """Review and atomically apply one operation-owned prepared value."""

    def review(self, prepared: PreparedT) -> PreparedT | None:
        """Return the exact reviewed value, or None without applying it."""

    def apply(self, reviewed: PreparedT) -> AppliedT:
        """Revalidate and publish the reviewed value through one transaction."""


@dataclass(frozen=True)
class ApplicationFlowResult(Generic[PreparedT, AppliedT]):
    """Typed evidence for the terminal phase reached by one application run."""

    status: ApplicationFlowStatus
    prepared: PreparedT
    reviewed: PreparedT | None
    applied: AppliedT | None

    def __post_init__(self) -> None:
        if self.status == "CANCELLED":
            if self.reviewed is not None or self.applied is not None:
                raise ValueError("A cancelled application cannot publish phase values.")
            return
        if self.status != "APPLIED":
            raise ValueError("Application flow status is invalid.")
        if self.reviewed is None or self.applied is None:
            raise ValueError("An applied flow requires reviewed and applied values.")


def run_application_flow(
    prepared: PreparedT,
    *,
    port: ApplicationFlowPort[PreparedT, AppliedT],
) -> ApplicationFlowResult[PreparedT, AppliedT]:
    """Run PREPARED -> REVIEWED -> APPLIED without owning operation meaning.

    The port's ``apply`` method is the atomic boundary: it must revalidate the
    exact reviewed value and return only after its operation-specific receipt
    is durable. Exceptions propagate and therefore never produce a misleading
    APPLIED flow result.
    """

    if prepared is None:
        raise TypeError("Application flow requires a prepared value.")
    reviewed = port.review(prepared)
    if reviewed is None:
        return ApplicationFlowResult(
            status="CANCELLED",
            prepared=prepared,
            reviewed=None,
            applied=None,
        )
    applied = port.apply(reviewed)
    if applied is None:
        raise TypeError("Application port returned no applied receipt.")
    return ApplicationFlowResult(
        status="APPLIED",
        prepared=prepared,
        reviewed=reviewed,
        applied=applied,
    )
