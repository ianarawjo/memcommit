"""Convert Audit findings into Resolve issues and expose their keys."""

from ..model import AuditResolutionIssue
from memcommit.application.operations.audit.model import QualityAuditSession
from .resolution_options.catalog import AUDIT_PROJECTIONS


def collect_resolution_issues(
    audit: QualityAuditSession,
) -> tuple[AuditResolutionIssue, ...]:
    check_kinds = {"ambiguities": "AMBIGUITY", "conflicts": "CONFLICT"}
    # Consolidate DUP/DUN once; preserve Audit order for the remaining projections.
    kinds = (
        "REDUNDANCY",
        *(
            check_kinds[check.kind]
            for check in audit.checks
            if check.kind not in {"dup", "dun"}
        ),
    )
    return tuple(item for kind in kinds for item in AUDIT_PROJECTIONS[kind](audit))


def all_audit_issue_keys(audit: QualityAuditSession) -> tuple[str, ...]:
    """Return every actionable semantic key in one complete Audit."""

    return tuple(item.audit_key for item in collect_resolution_issues(audit))
