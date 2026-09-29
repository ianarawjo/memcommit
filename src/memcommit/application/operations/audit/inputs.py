"""Inputs for running and recording an Audit of one readable Context."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.audit.model import (
    AuditCheckKind,
    QualityAuditError,
)


@dataclass(frozen=True)
class AuditRequest:
    """Context locators and optional checks; None requests the standard checks."""

    context_name: str | None = None
    checks: frozenset[AuditCheckKind] | None = None

    def __post_init__(self) -> None:
        if self.checks is None:
            return
        if not isinstance(self.checks, frozenset) or any(
            not isinstance(kind, AuditCheckKind) for kind in self.checks
        ):
            raise QualityAuditError(
                "Audit checks must be a frozenset of AuditCheckKind values."
            )
        if not self.checks:
            raise QualityAuditError("Audit must request at least one check.")
