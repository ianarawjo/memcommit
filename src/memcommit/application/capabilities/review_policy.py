"""Ownership-aware final-review policy for reversible application effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DecisionFreeBehavior = Literal["REPORT_FIRST", "FINAL_REVIEW", "AUTO_ACCEPT"]


@dataclass(frozen=True)
class ApplicationReviewPolicy:
    """Describe what to do when no semantic decision remains unanswered."""

    decision_free_behavior: DecisionFreeBehavior
    mutation_boundary: Literal["NONE", "LOCAL"]
    recovery: str

    def __post_init__(self) -> None:
        if self.decision_free_behavior not in {
            "REPORT_FIRST",
            "FINAL_REVIEW",
            "AUTO_ACCEPT",
        }:
            raise ValueError("Application review behavior is invalid.")
        if self.mutation_boundary not in {
            "NONE",
            "LOCAL",
        }:
            raise ValueError("Application mutation boundary is invalid.")
        if not isinstance(self.recovery, str) or not self.recovery.strip():
            raise ValueError("Application review recovery must be nonempty text.")


def ownership_aware_application_review(
    *,
    local_undo_available: bool,
    publishes_context_mutation: bool = True,
) -> ApplicationReviewPolicy:
    """Let complete local Undo support decision-free application; otherwise retain review."""

    if type(local_undo_available) is not bool:
        raise TypeError("Local Undo metadata must be boolean.")
    if type(publishes_context_mutation) is not bool:
        raise TypeError("Context-mutation metadata must be boolean.")
    if not publishes_context_mutation:
        return ApplicationReviewPolicy(
            decision_free_behavior="AUTO_ACCEPT",
            mutation_boundary="NONE",
            recovery="NO CONTEXT MUTATION",
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
