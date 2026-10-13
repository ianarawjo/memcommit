"""Validate submitted choices and finalize the decisions for one review round."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from ..model import ResolveAnalysis, ResolveError
from ..analysis.resolution_options.catalog import (
    build_resolution_options,
)


ResolveDecisionKind = Literal[
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
class ResolveDecision:
    """One explicit human decision for one frozen Audit direction."""

    issue_uid: str
    kind: ResolveDecisionKind
    intent: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.issue_uid, str) or not self.issue_uid.strip():
            raise ResolveError("A Resolve decision requires an Issue uid.")
        if self.kind not in {
            "CONFIRM",
            "INTENT",
            "FORCE",
            "KEEP_TARGET",
            "TAKE_SOURCE",
            "KEEP_BOTH",
            "KEEP_AS_IS",
        }:
            raise ResolveError("A Resolve decision kind is invalid.")
        if not isinstance(self.intent, str):
            raise TypeError("Resolve intent must be text.")
        if self.kind == "INTENT" and not self.intent.strip():
            raise ResolveError("PROVIDE YOUR INTENT requires nonblank text.")
        if self.kind != "INTENT" and self.intent:
            raise ResolveError("Only PROVIDE YOUR INTENT may carry response text.")


@dataclass(frozen=True, slots=True)
class ResolveDecisionSet:
    """Submitted decisions bound to one frozen Resolve revision."""

    revision: str
    decisions: tuple[ResolveDecision, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision:
            raise ResolveError("Resolve decisions require a frozen revision.")
        if not isinstance(self.decisions, tuple) or any(
            not isinstance(value, ResolveDecision) for value in self.decisions
        ):
            raise TypeError("Resolve decisions must be typed values.")
        if len({decision.issue_uid for decision in self.decisions}) != len(
            self.decisions
        ):
            raise ResolveError("Resolve decisions must name each Issue once.")

    @property
    def forced_issue_uids(self) -> tuple[str, ...]:
        return tuple(
            decision.issue_uid
            for decision in self.decisions
            if decision.kind == "FORCE"
        )


@dataclass(frozen=True, slots=True)
class ResolveFinalizedInput:
    """Exact semantic input retained in the Resolve checkpoint."""

    issue_uid: str
    kind: ResolveDecisionKind
    content: str

    def to_dict(self) -> dict[str, str]:
        return {
            "issue_uid": self.issue_uid,
            "kind": self.kind,
            "content": self.content,
        }


def finalize_resolve_decisions(
    analysis: ResolveAnalysis,
    decisions: tuple[ResolveDecision, ...],
) -> ResolveDecisionSet:
    """Validate submitted choices; unanswered issues remain for post-change Audit."""

    if not isinstance(analysis, ResolveAnalysis):
        raise TypeError("Resolve finalization requires a typed analysis.")
    result = ResolveDecisionSet(analysis.frame.revision, decisions)
    expected = tuple(issue.uid for issue in analysis.issues)
    actual = tuple(decision.issue_uid for decision in result.decisions)
    unknown = set(actual) - set(expected)
    if unknown:
        raise ResolveError(
            "Resolve decisions name unknown issues: " + ", ".join(sorted(unknown))
        )
    if expected and not actual:
        raise ResolveError("Review changes requires at least one explicit decision.")
    by_uid = {decision.issue_uid: decision for decision in result.decisions}
    for issue in analysis.issues:
        if issue.uid not in by_uid:
            continue
        if (
            issue.kind == "REDUNDANCY"
            and by_uid[issue.uid].kind == "CONFIRM"
            and "DELETE" not in analysis.frame.allowed_effects
        ):
            raise ResolveError("Keeping one duplicate requires DELETE authority.")
        if issue.kind == "REDUNDANCY":
            allowed = {
                choice.uid for choice in build_resolution_options(analysis, issue)
            }
        elif issue.choices:
            allowed = {choice.uid for choice in issue.choices}
        else:
            allowed = {
                "CONFIRM",
                "INTENT",
                "FORCE",
                "KEEP_AS_IS" if len(issue.item_uids) == 1 else "KEEP_BOTH",
            }
        if by_uid[issue.uid].kind not in allowed:
            raise ResolveError("Resolve decision is unavailable for this Audit item.")
    return ResolveDecisionSet(
        revision=result.revision,
        decisions=tuple(by_uid[uid] for uid in expected if uid in by_uid),
    )


__all__ = [
    "ResolveDecision",
    "ResolveDecisionKind",
    "ResolveDecisionSet",
    "ResolveFinalizedInput",
    "finalize_resolve_decisions",
]
