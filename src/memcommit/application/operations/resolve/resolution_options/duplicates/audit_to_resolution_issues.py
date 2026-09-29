"""Project Audit duplicates into Resolve issue inputs without rechecking them."""

from __future__ import annotations

from memcommit.application.operations.audit.model import QualityAuditSession
from ...model import AuditResolutionIssue
from memcommit.application.operations.audit.findings import audit_redundancies


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
