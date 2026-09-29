"""Project Audit ambiguities into Resolve issue inputs without rechecking them."""

from __future__ import annotations

from memcommit.application.operations.audit.model import QualityAuditSession
from ...model import AuditResolutionIssue
from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityReport,
)


def audit_to_resolution_issues(
    audit: QualityAuditSession,
) -> tuple[AuditResolutionIssue, ...]:
    result = []
    for check in audit.checks:
        if check.kind != "ambiguities":
            continue
        report = check.report
        assert isinstance(report, AmbiguityReport)
        for finding in report.findings:
            result.append(
                AuditResolutionIssue(
                    audit_snapshot_digest=audit.snapshot_digest,
                    audit_key=f"AMBIGUITY:{finding.memory.uid}",
                    kind="AMBIGUITY",
                    classification=f"{finding.interpretation} · {finding.clarification}",
                    item_uids=(finding.memory.uid,),
                    reason=finding.reason,
                    question=finding.question,
                    detail={"ordinary_readings": list(finding.ordinary_readings)},
                )
            )
    return tuple(result)
