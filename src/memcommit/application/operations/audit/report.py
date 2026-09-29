"""Project typed Audit checks through the shared read-only finding document."""

from dataclasses import replace

from memcommit.application.capabilities.memory_issue_analysis.model import (
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.application.capabilities.memory_issue_analysis.report import (
    QualityFindReportView,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.application.capabilities.memory_issue_analysis.workbench import (
    QualityFindWorkbenchSession,
    quality_find_report_view,
)
from memcommit.application.operations.audit.model import (
    QualityAuditCheck,
    QualityAuditSession,
)
from memcommit.application.operations.duplicates.find_duplicates.application import (
    ExactDuplicateReport,
)
from memcommit.core.context import Memory


def audit_check_label(kind: str) -> str:
    return {
        "dup": "DUP",
        "dun": "DUN",
        "ambiguities": "AMBIGUITIES",
        "conflicts": "CONFLICTS",
    }[kind]


def ordered_audit_checks(session: QualityAuditSession) -> tuple[QualityAuditCheck, ...]:
    """Present the review priority without changing execution or record ordering."""
    order = {"conflicts": 0, "ambiguities": 1, "dup": 2, "dun": 3}
    return tuple(sorted(session.checks, key=lambda check: order[check.kind]))


def audit_check_report_view(
    session: QualityAuditSession, check: QualityAuditCheck
) -> QualityFindReportView:
    context = session.source.context()
    report = check.report
    kind = check.kind
    if isinstance(report, ExactDuplicateReport):
        memories = {
            item.uid: item for item in context.iter_items() if isinstance(item, Memory)
        }
        report = DuplicateReport(
            memory_count=report.memory_count,
            findings=tuple(
                DuplicateFinding(
                    memories[group.survivor_uid],
                    memories[uid],
                    "EXACT",
                    "Stored content is identical.",
                )
                for group in report.groups
                if group.item_kind == "MEMORY"
                for uid in group.absorbed_uids
            ),
            exact_item_groups=tuple(
                group for group in report.groups if group.item_kind != "MEMORY"
            ),
        )
    if kind in {"dup", "dun"}:
        kind = "duplicates"
    source = QualityFindSourceFrame.create((context,))
    view = quality_find_report_view(
        QualityFindWorkbenchSession(
            uid=session.uid, kind=kind, source=source, report=report
        ),
        context,
        operation_label=f"AUDIT · {audit_check_label(check.kind)}",
    )

    if check.kind in {"dup", "dun"} and len(session.source.items) != len(
        session.source.memories
    ):
        return replace(view, direct_item_count=len(session.source.items))
    return view
