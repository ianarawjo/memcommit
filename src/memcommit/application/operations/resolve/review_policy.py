"""Select the next review tier and honor decisions to retain unchanged content."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .decisions import KEEP_DECISIONS
from .issues import audit_issue_signatures, collect_resolution_issues

if TYPE_CHECKING:
    from memcommit.application.operations.audit.model import QualityAuditSession
    from .issue_review import IssueReviewRound
    from .model import AuditResolutionIssue, FrozenResolveFrame


ISSUE_PRIORITY = {"CONFLICT": 1, "AMBIGUITY": 2, "REDUNDANCY": 3}


def forced_review_issues(
    audit: QualityAuditSession, rounds: tuple[IssueReviewRound, ...]
) -> tuple[tuple[str, str], ...]:
    """Keep FORCE's exact-finding waiver separate from content preservation."""
    current = audit_issue_signatures(audit)
    forced = {}
    for review in rounds:
        issues = {issue.uid: issue for issue in review.issues}
        signatures = audit_issue_signatures(review.audit)
        for decision in review.decisions.decisions:
            if decision.kind != "FORCE":
                continue
            issue = issues[decision.issue_uid]
            if issue.audit_key in current and current[
                issue.audit_key
            ] == signatures.get(issue.audit_key):
                forced[issue.audit_key] = issue.uid
    return tuple(forced.items())


def remaining_review_issues(
    audit: QualityAuditSession,
    *,
    rounds: tuple[IssueReviewRound, ...] = (),
    frame: FrozenResolveFrame | None = None,
) -> tuple[AuditResolutionIssue, ...]:
    """Return unanswered findings without changing the complete Audit evidence."""
    current = audit.source.context()
    retained = []
    for review in rounds:
        before = review.before()
        if before.uid != current.uid:
            continue
        issues = {issue.uid: issue for issue in review.issues}
        for decision in review.decisions.decisions:
            if decision.kind not in KEEP_DECISIONS:
                continue
            issue = issues[decision.issue_uid]
            members = frozenset(issue.item_uids)
            # Labels can drift or disappear between audits. Only changed evidence
            # revokes a keep decision; its scope never grows to include a new member.
            if members and all(
                uid in current.memories
                and current.memories[uid].to_dict() == before.memories[uid].to_dict()
                for uid in members
            ):
                retained.append((ISSUE_PRIORITY[issue.kind], issue.item_kind, members))

    forced = dict(forced_review_issues(audit, rounds))
    return tuple(
        issue
        for issue in collect_resolution_issues(frame, audit)
        if issue.audit_key not in forced
        and not any(
            ISSUE_PRIORITY[issue.kind] >= priority
            and issue.item_kind == item_kind
            and bool(issue.item_uids)
            and set(issue.item_uids) <= members
            for priority, item_kind, members in retained
        )
    )


def select_round_issues(
    issues: tuple[AuditResolutionIssue, ...],
) -> tuple[AuditResolutionIssue, ...]:
    """Ask only the highest remaining tier; lower findings may disappear on recheck."""
    if not issues:
        return ()
    priority = min(ISSUE_PRIORITY[issue.kind] for issue in issues)
    return tuple(issue for issue in issues if ISSUE_PRIORITY[issue.kind] == priority)
