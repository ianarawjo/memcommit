"""Normalize overlapping DUP/DUN evidence into one set of resolution items."""

from dataclasses import dataclass
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.duplicates.find_duplicates.application import (
    ExactDuplicateReport,
)
from memcommit.application.capabilities.memory_issue_analysis.model import (
    DuplicateReport,
)


@dataclass(frozen=True)
class AuditRedundancy:
    item_kind: str
    item_uids: tuple[str, ...]
    classification: str
    reason: str

    @property
    def key(self) -> str:
        prefix = "REDUNDANCY" if self.item_kind == "MEMORY" else "DUP:" + self.item_kind
        return prefix + ":" + ":".join(sorted(self.item_uids))


def audit_redundancies(audit: QualityAuditSession) -> tuple[AuditRedundancy, ...]:
    result = {}
    for check in audit.checks:
        report = check.report
        if isinstance(report, ExactDuplicateReport):
            groups = report.groups
        elif isinstance(report, DuplicateReport):
            for finding in report.findings:
                item = AuditRedundancy(
                    "MEMORY",
                    (finding.left.uid, finding.right.uid),
                    finding.relation,
                    finding.reason,
                )
                result.setdefault(item.key, item)
            groups = report.exact_item_groups
        else:
            continue
        for group in groups:
            # Exact Memory edges use the same first-occurrence forest as DUN;
            # pointer groups retain their complete same-role membership.
            members = (
                ((group.survivor_uid, uid) for uid in group.absorbed_uids)
                if group.item_kind == "MEMORY"
                else ((group.survivor_uid, *group.absorbed_uids),)
            )
            for uids in members:
                item = AuditRedundancy(
                    group.item_kind,
                    uids,
                    "EXACT",
                    "Stored content is identical."
                    if group.item_kind == "MEMORY"
                    else "These direct occurrences have the same role and target identity: "
                    + group.summary,
                )
                result.setdefault(item.key, item)
    return tuple(result.values())
