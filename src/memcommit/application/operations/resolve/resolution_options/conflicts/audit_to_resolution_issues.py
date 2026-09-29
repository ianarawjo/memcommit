"""Project Audit conflicts into Resolve issue inputs without rechecking them."""

from __future__ import annotations

from memcommit.application.operations.audit.model import QualityAuditSession
from ...model import AuditResolutionIssue
from memcommit.application.capabilities.memory_issue_analysis.model import (
    ConflictReport,
)


def audit_to_resolution_issues(
    audit: QualityAuditSession,
) -> tuple[AuditResolutionIssue, ...]:
    result = []
    for check in audit.checks:
        if check.kind != "conflicts":
            continue
        report = check.report
        assert isinstance(report, ConflictReport)
        for finding in report.findings:
            members = (finding.left.uid, finding.right.uid)
            result.append(
                AuditResolutionIssue(
                    audit_snapshot_digest=audit.snapshot_digest,
                    audit_key="CONFLICT:" + ":".join(sorted(members)),
                    kind="CONFLICT",
                    classification=finding.conflict,
                    item_uids=members,
                    reason=finding.reason,
                    question="",
                    detail={},
                )
            )
    return tuple(result)
