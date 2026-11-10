"""Convert conflict-only Audit findings into issues with stable keys."""

from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.capabilities.memory_issue_analysis.model import (
    ConflictReport,
)
from ..model import AuditResolutionIssue, ConflictResolutionError


def collect_resolution_issues(
    audit: QualityAuditSession,
) -> tuple[AuditResolutionIssue, ...]:
    if tuple(check.kind for check in audit.checks) != ("conflicts",):
        raise ConflictResolutionError("Conflict requires a conflicts-only Audit.")
    report = audit.checks[0].report
    assert isinstance(report, ConflictReport)
    return tuple(
        AuditResolutionIssue(
            audit_snapshot_digest=audit.snapshot_digest,
            audit_key="CONFLICT:"
            + ":".join(sorted((finding.left.uid, finding.right.uid))),
            kind="CONFLICT",
            classification=finding.conflict,
            item_uids=(finding.left.uid, finding.right.uid),
            reason=finding.reason,
            question="",
            detail={},
        )
        for finding in report.findings
    )


def all_audit_issue_keys(audit: QualityAuditSession) -> tuple[str, ...]:
    return tuple(item.audit_key for item in collect_resolution_issues(audit))
