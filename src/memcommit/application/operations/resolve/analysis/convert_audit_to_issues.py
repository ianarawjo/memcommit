"""Convert Audit findings into Resolve issues and expose their keys."""

from ..model import AuditResolutionIssue, ResolveTarget
from memcommit.application.operations.audit.model import QualityAuditSession
from .resolution_options.catalog import AUDIT_PROJECTIONS


def collect_resolution_issues(
    frame: ResolveTarget | None,
    audit: QualityAuditSession,
) -> tuple[AuditResolutionIssue, ...]:
    all_uids = {item.uid for item in audit.source.items}
    actionable = set(frame.actionable_uids) if frame is not None else all_uids
    all_actionable = actionable == all_uids
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
    return tuple(
        item
        for kind in kinds
        for item in AUDIT_PROJECTIONS[kind](audit)
        if actionable.intersection(item.item_uids)
        or (not item.item_uids and all_actionable)
    )


def resolve_audit_item_keys(
    frame: ResolveTarget,
    audit: QualityAuditSession,
) -> tuple[str, ...]:
    """Expose exact semantic keys for post-image verification."""

    return tuple(item.audit_key for item in collect_resolution_issues(frame, audit))


def all_audit_issue_keys(audit: QualityAuditSession) -> tuple[str, ...]:
    """Return every actionable semantic key in one complete Audit."""

    return tuple(item.audit_key for item in collect_resolution_issues(None, audit))
