"""Operation-neutral decision-to-application phase orchestration.

The flow deliberately owns only phase order. Operation adapters retain the
meaning of decisions, freshness, authority, CAS, rollback, checkpoints,
receipts, and recovery. Post-application Review is deliberately outside this
module: it consumes a terminal receipt instead of participating in execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar


PreparedT = TypeVar("PreparedT")
AppliedT = TypeVar("AppliedT")
ApplicationFlowStatus = Literal["CANCELLED", "APPLIED"]


class ApplicationFlowPort(Protocol[PreparedT, AppliedT]):
    """Resolve execution decisions and atomically apply one prepared value."""

    def decide(self, prepared: PreparedT) -> PreparedT | None:
        """Return the exact decided value, or None without applying it."""

    def apply(self, decided: PreparedT) -> AppliedT:
        """Revalidate and publish the decided value through one transaction."""


@dataclass(frozen=True)
class ApplicationFlowResult(Generic[PreparedT, AppliedT]):
    """Typed evidence for the terminal phase reached by one application run."""

    status: ApplicationFlowStatus
    prepared: PreparedT
    decided: PreparedT | None
    applied: AppliedT | None

    def __post_init__(self) -> None:
        if self.status == "CANCELLED":
            if self.decided is not None or self.applied is not None:
                raise ValueError("A cancelled application cannot publish phase values.")
            return
        if self.status != "APPLIED":
            raise ValueError("Application flow status is invalid.")
        if self.decided is None or self.applied is None:
            raise ValueError("An applied flow requires decided and applied values.")

    @property
    def reviewed(self) -> PreparedT | None:
        """Compatibility projection while callers migrate to ``decided``.

        New execution code must not use this name. Review is a
        post-application, receipt-bound read operation; this value is only the
        decision-complete input consumed by Apply.
        """

        return self.decided


def run_application_flow(
    prepared: PreparedT,
    *,
    port: ApplicationFlowPort[PreparedT, AppliedT],
) -> ApplicationFlowResult[PreparedT, AppliedT]:
    """Run PREPARED -> DECIDED -> APPLIED without owning operation meaning.

    The port's ``apply`` method is the atomic boundary: it must revalidate the
    exact decided value and return only after its operation-specific receipt
    is durable. Exceptions propagate and therefore never produce a misleading
    APPLIED flow result.
    """

    if prepared is None:
        raise TypeError("Application flow requires a prepared value.")
    decided = port.decide(prepared)
    if decided is None:
        return ApplicationFlowResult(
            status="CANCELLED",
            prepared=prepared,
            decided=None,
            applied=None,
        )
    applied = port.apply(decided)
    if applied is None:
        raise TypeError("Application port returned no applied receipt.")
    return ApplicationFlowResult(
        status="APPLIED",
        prepared=prepared,
        decided=decided,
        applied=applied,
    )
