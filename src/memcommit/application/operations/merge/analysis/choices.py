"""Construct and validate fixed responses to Merge's structural findings."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from memcommit.application.capabilities.resolution.workbench import ResolutionOption

from ..inputs import StructuralAddition, StructuralConflict, StructuralResolutionInput
from .candidate import MergeCandidate
from .conflicts import MergeConflictReport

if TYPE_CHECKING:
    from ..result import LiteralMergeReview

EXACT_DECISIONS = frozenset({"KEEP_TARGET", "TAKE_SOURCE", "KEEP_BOTH"})


@dataclass(frozen=True, slots=True)
class MergeConflictDecision:
    issue_uid: str
    kind: str

    def __post_init__(self):
        if not self.issue_uid or self.kind not in EXACT_DECISIONS:
            raise ValueError("Invalid structural Merge decision.")


@dataclass(frozen=True, slots=True)
class MergeDecisionSet:
    revision: str
    decisions: tuple[MergeConflictDecision, ...]

    def __post_init__(self):
        if (
            not self.revision
            or not isinstance(self.decisions, tuple)
            or any(
                not isinstance(item, MergeConflictDecision) for item in self.decisions
            )
        ):
            raise ValueError(
                "Merge decisions require their revision and typed choices."
            )
        if len({item.issue_uid for item in self.decisions}) != len(self.decisions):
            raise ValueError("Merge decisions must name each conflict once.")


@dataclass(frozen=True, slots=True)
class MergeConflictIssue:
    uid: str
    classification: str
    item_uids: tuple[str, ...]
    item_kind: str
    reason: str
    choices: tuple[ResolutionOption, ...]
    default_choice: str = "KEEP_TARGET"
    kind: str = "MERGE_CONFLICT"
    question: str = "Which version should the destination retain?"


@dataclass(frozen=True, slots=True)
class MergeConflictAnalysis:
    candidate: MergeCandidate
    report: MergeConflictReport
    issues: tuple[MergeConflictIssue, ...]

    @property
    def revision(self):
        return self.candidate.revision

    @property
    def review_issues(self):
        return self.issues


def finalize_merge_decisions(analysis, decisions):
    result = MergeDecisionSet(analysis.revision, decisions)
    expected = {issue.uid: issue for issue in analysis.issues}
    actual = {decision.issue_uid: decision for decision in result.decisions}
    if actual.keys() != expected.keys():
        raise ValueError("FINALIZE DECISIONS requires one response per Merge conflict.")
    for uid, issue in expected.items():
        if actual[uid].kind not in {choice.uid for choice in issue.choices}:
            raise ValueError("Merge decision is unavailable for this conflict.")
    return MergeDecisionSet(result.revision, tuple(actual[uid] for uid in expected))


def prepare_structural_input(
    candidate,
    report,
    *,
    source,
    target,
    revision,
    policy,
    defer_target_validation=False,
):
    """Derive exact options and freeze allocation once for either Merge method."""
    additions = tuple(
        StructuralAddition(
            candidate.origin(uid).item_uid,
            str(uuid.uuid4()),
        )
        for uid in report.additions
    )
    if (
        additions
        and not defer_target_validation
        and (not policy.context_mutable or "CREATE" not in policy.allowed_effects)
    ):
        if not policy.context_mutable:
            raise ValueError(f"Context '{target.name}' is locked against changes.")
        raise ValueError(
            "Target does not permit CREATE for the required Merge additions."
        )
    conflicts, choices = prepare_structural_choices(candidate, report, policy=policy)
    return StructuralResolutionInput(
        revision,
        json.dumps(source.to_dict()),
        json.dumps(target.to_dict()),
        additions,
        conflicts,
    ), choices


def prepare_structural_choices(candidate, report, *, policy):
    """Derive exact responses from the current findings and frozen Target policy."""
    conflicts, choices = [], {}
    for finding in report.findings:
        source_item = candidate.original_item(finding.source_uid)
        targets = tuple(candidate.original_item(uid) for uid in finding.target_uids)
        allowed = ["KEEP_TARGET"]
        mutable = policy.context_mutable and not any(
            item.uid in policy.protected_uids for item in targets
        )
        if mutable and "UPDATE" in policy.allowed_effects:
            allowed.append("TAKE_SOURCE")
        both_uid = None
        if policy.context_mutable and "CREATE" in policy.allowed_effects:
            allowed.append("KEEP_BOTH")
            both_uid = str(uuid.uuid4())
        conflicts.append(
            StructuralConflict(
                finding.uid,
                source_item.uid,
                tuple(item.uid for item in targets),
                tuple(allowed),
                both_uid,
            )
        )

        def text(choice):
            members = (finding.target_uids if choice != "TAKE_SOURCE" else ()) + (
                (finding.source_uid,) if choice != "KEEP_TARGET" else ()
            )
            lines = []
            for uid in members:
                origin, item = candidate.origin(uid), candidate.original_item(uid)
                lines.append(
                    f"[{origin.context_name}:{origin.item_uid[:8]}] {item.content}"
                )
            return "\n".join(lines)

        choices[finding.uid] = tuple(
            ResolutionOption(value, value.replace("_", " "), text(value))
            for value in allowed
        )
    return tuple(conflicts), choices


def merge_sides(candidate, issue):
    origins = [candidate.origin(uid) for uid in issue.item_uids]
    targets = tuple(
        origin.uid for origin in origins if origin.context_name == origin.placement
    )
    sources = tuple(
        origin.uid for origin in origins if origin.context_name != origin.placement
    )
    return targets, sources


def initial_review_decisions(review: LiteralMergeReview, choice: str | None):
    """Validate a bulk structural choice after structural analysis has produced the conflicts."""
    if choice is None:
        return None
    decisions = tuple(
        MergeConflictDecision(issue.uid, choice)
        for issue in review.analysis.review_issues
    )
    finalize_merge_decisions(review.analysis, decisions)
    return decisions
