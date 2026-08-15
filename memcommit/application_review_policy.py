"""Ownership-aware final-review policy for reversible application effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DecisionFreeBehavior = Literal["REPORT_FIRST", "FINAL_REVIEW", "AUTO_ACCEPT"]


@dataclass(frozen=True)
class ApplicationReviewPolicy:
    """Describe what to do when no semantic decision remains unanswered."""

    decision_free_behavior: DecisionFreeBehavior
    mutation_boundary: Literal["LOCAL", "GRANTED_AUTHORITY"]
    recovery: str

    def __post_init__(self) -> None:
        if self.decision_free_behavior not in {
            "REPORT_FIRST",
            "FINAL_REVIEW",
            "AUTO_ACCEPT",
        }:
            raise ValueError("Application review behavior is invalid.")
        if self.mutation_boundary not in {"LOCAL", "GRANTED_AUTHORITY"}:
            raise ValueError("Application mutation boundary is invalid.")
        if not isinstance(self.recovery, str) or not self.recovery.strip():
            raise ValueError("Application review recovery must be nonempty text.")


def ownership_aware_application_review(
    *,
    mutates_granted_authority: bool,
    local_undo_available: bool,
) -> ApplicationReviewPolicy:
    """Keep authority writes explicit; let reversible local writes use Undo.

    Reading granted input does not make a derived local result an authority
    mutation. The boundary follows the Context that will actually be written.
    """

    if type(mutates_granted_authority) is not bool:
        raise TypeError("Authority-mutation metadata must be boolean.")
    if type(local_undo_available) is not bool:
        raise TypeError("Local Undo metadata must be boolean.")
    if mutates_granted_authority:
        return ApplicationReviewPolicy(
            decision_free_behavior="FINAL_REVIEW",
            mutation_boundary="GRANTED_AUTHORITY",
            recovery="EXPLICIT REVIEW BEFORE AUTHORITY WRITE",
        )
    if local_undo_available:
        return ApplicationReviewPolicy(
            decision_free_behavior="AUTO_ACCEPT",
            mutation_boundary="LOCAL",
            recovery="MEM UNDO",
        )
    return ApplicationReviewPolicy(
        decision_free_behavior="FINAL_REVIEW",
        mutation_boundary="LOCAL",
        recovery="EXPLICIT REVIEW; NO COMPLETE LOCAL UNDO RECEIPT",
    )
