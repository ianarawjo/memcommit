"""Honor Conflict decisions to retain unchanged content and waive exact findings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..review_round.finalize_review_decisions import KEEP_DECISIONS
from .convert_audit_to_issues import collect_resolution_issues

if TYPE_CHECKING:
    from memcommit.application.operations.audit.model import QualityAuditSession
    from memcommit.application.operations.conflict.review_round.review_round_record import (
        ReviewRoundRecord,
    )
    from ..model import AuditResolutionIssue, ConflictResolutionTarget


def audit_issue_signatures(audit):
    """Bind accepted findings to their kind, classification and exact member bytes."""
    from memcommit.application.operations.merge.analysis.candidate import digest

    records = {item.uid: item.summary for item in audit.source.items}
    return {
        item.audit_key: digest(
            {
                "key": item.audit_key,
                "kind": item.kind,
                "classification": item.classification,
                # Whole-Context findings may not nominate individual members.
                "members": [
                    (uid, records[uid]) for uid in (item.item_uids or tuple(records))
                ],
                "rule": item.detail.get("rule"),
            }
        )
        for item in collect_resolution_issues(audit)
    }


def forced_review_issues(
    audit: QualityAuditSession, rounds: tuple[ReviewRoundRecord, ...]
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
    rounds: tuple[ReviewRoundRecord, ...] = (),
    frame: ConflictResolutionTarget | None = None,
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
                retained.append(members)

    forced = dict(forced_review_issues(audit, rounds))
    return tuple(
        issue
        for issue in collect_resolution_issues(audit)
        if issue.audit_key not in forced
        and not any(set(issue.item_uids) <= members for members in retained)
    )
