"""Own redundancy projection, fixed directions, choices, and exact removal plans."""

from __future__ import annotations

from typing import TYPE_CHECKING
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.audit.findings import audit_redundancies
from memcommit.application.capabilities.resolution.workbench import ResolutionOption
from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.update.model import RemoveOperation, UpdatePlan
from ....model import AuditResolutionIssue, ResolveError

if TYPE_CHECKING:
    from ....model import ResolveAnalysis, ResolveIssue


def audit_to_resolution_issues(
    audit: QualityAuditSession,
) -> tuple[AuditResolutionIssue, ...]:
    return tuple(
        AuditResolutionIssue(
            audit_snapshot_digest=audit.snapshot_digest,
            audit_key=finding.key,
            kind="REDUNDANCY",
            classification=finding.classification,
            item_uids=finding.item_uids,
            item_kind=finding.item_kind,
            reason=finding.reason,
            question="",
            detail={},
        )
        for finding in audit_redundancies(audit)
    )


def build_fixed_suggestion(item: AuditResolutionIssue) -> str:
    return (
        f"Keep the first Memory [{item.item_uids[0][:8]}] unchanged and delete the duplicate "
        + ", ".join((f"[{uid[:8]}]" for uid in item.item_uids[1:]))
        + "."
    )


def build_resolution_choices(
    analysis: ResolveAnalysis, issue: ResolveIssue
) -> tuple[ResolutionOption, ...]:
    choices = []
    if "DELETE" in analysis.frame.allowed_effects:
        choices.append(("CONFIRM", "KEEP ONE", issue.proposed_direction))
    choices.append(
        (
            "KEEP_BOTH" if len(issue.item_uids) > 1 else "KEEP_AS_IS",
            "KEEP BOTH" if len(issue.item_uids) > 1 else "KEEP AS IS",
            "Preserve the current texts.",
        )
    )
    return tuple(
        (
            ResolutionOption(kind, label, description)
            for kind, label, description in choices
        )
    )


def duplicate_choice_plan(analysis, decisions, target) -> UpdatePlan:
    issues = {issue.uid: issue for issue in analysis.issues}
    removed = {}
    for decision in decisions.decisions:
        issue = issues[decision.issue_uid]
        if issue.kind != "REDUNDANCY" or decision.kind != "CONFIRM":
            continue
        if "DELETE" not in analysis.frame.allowed_effects:
            raise ResolveError("Keeping one duplicate requires DELETE authority.")
        for uid in issue.item_uids[1:]:
            removed[uid] = RemoveOperation(
                owner_context_uid=target.uid,
                owner_context_name=target.name,
                memory_uid=uid,
                old_content=target.memories[uid].content,
                source_refs=(),
                reason=issue.proposed_direction,
            )
    return UpdatePlan(
        "resolve-duplicates-" + digest([op.to_dict() for op in removed.values()]),
        target.uid,
        target.name,
        tuple(removed.values()),
    )
