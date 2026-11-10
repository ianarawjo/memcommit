"""Validate submitted choices and finalize the decisions for one review round."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from ..model import ConflictResolutionAnalysis, ConflictResolutionError


ConflictResolutionDecisionKind = Literal[
    "CONFIRM",
    "INTENT",
    "FORCE",
    "KEEP_TARGET",
    "TAKE_SOURCE",
    "KEEP_BOTH",
    "KEEP_AS_IS",
]

KEEP_DECISIONS = frozenset({"KEEP_BOTH", "KEEP_AS_IS"})


@dataclass(frozen=True, slots=True)
class ConflictResolutionDecision:
    """One explicit human decision for one frozen Audit direction."""

    issue_uid: str
    kind: ConflictResolutionDecisionKind
    intent: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.issue_uid, str) or not self.issue_uid.strip():
            raise ConflictResolutionError("A Conflict decision requires an Issue uid.")
        if self.kind not in {
            "CONFIRM",
            "INTENT",
            "FORCE",
            "KEEP_TARGET",
            "TAKE_SOURCE",
            "KEEP_BOTH",
            "KEEP_AS_IS",
        }:
            raise ConflictResolutionError("A Conflict decision kind is invalid.")
        if not isinstance(self.intent, str):
            raise TypeError("Conflict intent must be text.")
        if self.kind == "INTENT" and not self.intent.strip():
            raise ConflictResolutionError("PROVIDE YOUR INTENT requires nonblank text.")
        if self.kind != "INTENT" and self.intent:
            raise ConflictResolutionError(
                "Only PROVIDE YOUR INTENT may carry response text."
            )


@dataclass(frozen=True, slots=True)
class ConflictResolutionDecisionSet:
    """Submitted decisions bound to one frozen Conflict revision."""

    revision: str
    decisions: tuple[ConflictResolutionDecision, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision:
            raise ConflictResolutionError(
                "Conflict decisions require a frozen revision."
            )
        if not isinstance(self.decisions, tuple) or any(
            not isinstance(value, ConflictResolutionDecision)
            for value in self.decisions
        ):
            raise TypeError("Conflict decisions must be typed values.")
        if len({decision.issue_uid for decision in self.decisions}) != len(
            self.decisions
        ):
            raise ConflictResolutionError(
                "Conflict decisions must name each Issue once."
            )

    @property
    def forced_issue_uids(self) -> tuple[str, ...]:
        return tuple(
            decision.issue_uid
            for decision in self.decisions
            if decision.kind == "FORCE"
        )


@dataclass(frozen=True, slots=True)
class ConflictResolutionFinalizedInput:
    """Exact semantic input retained in the Conflict checkpoint."""

    issue_uid: str
    kind: ConflictResolutionDecisionKind
    content: str

    def to_dict(self) -> dict[str, str]:
        return {
            "issue_uid": self.issue_uid,
            "kind": self.kind,
            "content": self.content,
        }


def finalize_conflict_resolution_decisions(
    analysis: ConflictResolutionAnalysis,
    decisions: tuple[ConflictResolutionDecision, ...],
) -> ConflictResolutionDecisionSet:
    """Validate submitted choices; unanswered issues remain for post-change Audit."""

    if not isinstance(analysis, ConflictResolutionAnalysis):
        raise TypeError("Conflict finalization requires a typed analysis.")
    result = ConflictResolutionDecisionSet(analysis.frame.revision, decisions)
    expected = tuple(issue.uid for issue in analysis.issues)
    actual = tuple(decision.issue_uid for decision in result.decisions)
    unknown = set(actual) - set(expected)
    if unknown:
        raise ConflictResolutionError(
            "Conflict decisions name unknown issues: " + ", ".join(sorted(unknown))
        )
    if expected and not actual:
        raise ConflictResolutionError(
            "Review changes requires at least one explicit decision."
        )
    by_uid = {decision.issue_uid: decision for decision in result.decisions}
    for issue in analysis.issues:
        if issue.uid not in by_uid:
            continue
        if issue.choices:
            allowed = {choice.uid for choice in issue.choices}
        else:
            allowed = {
                "CONFIRM",
                "INTENT",
                "FORCE",
                "KEEP_AS_IS" if len(issue.item_uids) == 1 else "KEEP_BOTH",
            }
        if by_uid[issue.uid].kind not in allowed:
            raise ConflictResolutionError(
                "Conflict decision is unavailable for this Audit item."
            )
    return ConflictResolutionDecisionSet(
        revision=result.revision,
        decisions=tuple(by_uid[uid] for uid in expected if uid in by_uid),
    )


__all__ = [
    "ConflictResolutionDecision",
    "ConflictResolutionDecisionKind",
    "ConflictResolutionDecisionSet",
    "ConflictResolutionFinalizedInput",
    "finalize_conflict_resolution_decisions",
]
