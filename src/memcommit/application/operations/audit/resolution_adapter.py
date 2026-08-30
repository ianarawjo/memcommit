"""Operation-owned compatibility projection for retained Audit responses."""

from __future__ import annotations

from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionMetric,
    ResolutionOverviewSection,
    ResolutionWorkbenchView,
    resolution_overview_text,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.report import (
    quality_find_category_label,
    quality_find_report_summary_text,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.workbench import (
    QualityFindSourceFrame,
    QualityFindWorkbenchSession,
    quality_find_report_view,
    quality_find_resolution_view,
)
from memcommit.application.operations.audit.model import (
    QUALITY_AUDIT_KINDS,
    QualityAuditSession,
)


def quality_audit_resolution_view(
    session: QualityAuditSession,
) -> ResolutionWorkbenchView:
    """Compose the legacy Resolution-shaped compatibility projection."""

    ctx = session.source.context()
    source_frame = QualityFindSourceFrame.create((ctx,))
    items = []
    counts: dict[str, int] = {}
    summaries: dict[str, str] = {}
    for check in session.checks:
        sub_session = QualityFindWorkbenchSession(
            uid=session.uid,
            kind=check.kind,
            source=source_frame,
            report=check.report,
            responses=session.responses,
        )
        projected = quality_find_resolution_view(sub_session, ctx)
        items.extend(projected.items)
        counts[check.kind] = len(projected.items)
        summaries[check.kind] = quality_find_report_summary_text(
            quality_find_report_view(sub_session, ctx)
        )

    check_lines = [
        f"{quality_find_category_label(kind)} · FINISHED · {summaries[kind]}"
        for kind in QUALITY_AUDIT_KINDS
    ]
    provenance_lines = [
        f"{quality_find_category_label(check.kind)} · {check.ruleset_version} · "
        f"{check.provenance.display_name()}"
        for check in session.checks
    ]
    conformance = session.conformance
    check_total = 3
    if conformance is not None:
        check_total = 4
        check_lines.append(
            "CONFORMANCE · FINISHED · "
            f"{len(conformance.context_judgments)} Rules · "
            f"{conformance.issue_count} issues"
        )
        identity = conformance.provider_identity
        assert identity is not None
        provenance_lines.append(
            f"CONFORMANCE · {conformance.ruleset_version} · {identity.display_name()}"
        )
    checks_text = "\n".join(check_lines)
    provenance_text = "\n".join(provenance_lines)
    sections_list = [
        ResolutionOverviewSection(
            "summary",
            "AUDIT SUMMARY",
            (
                "All quality finders completed over the same saved direct "
                "Context snapshot. Each section retains its own Memory, pair, "
                "group, or absorption unit."
                + (
                    " Conformance evaluated the same Source against "
                    f"{len(conformance.rules)} frozen Rules."
                    if conformance is not None
                    else ""
                )
            ),
        ),
        ResolutionOverviewSection("checks", "CHECKS", checks_text),
        ResolutionOverviewSection(
            "scope",
            "AUDITED SOURCE",
            (
                f"{session.source.context_name} · {len(session.source.memories)} direct "
                "Memories as captured when this Audit ran. Descendants and "
                "embedded Contexts were not analyzed."
            ),
        ),
        ResolutionOverviewSection("provenance", "PROVENANCE", provenance_text),
        ResolutionOverviewSection(
            "boundary",
            "BOUNDARY",
            (
                "This saved Audit is a model-assisted finding record, not proof "
                "that the Source is free of quality problems. Saved historical "
                "review notes do not alter the snapshot, Context, or Memories."
            ),
        ),
    ]
    if conformance is not None:
        rule_by_uid = {rule.uid: rule for rule in conformance.rules}
        sections_list.insert(
            3,
            ResolutionOverviewSection(
                "conformance",
                "CONFORMANCE",
                "\n".join(
                    f"{rule_by_uid[item.rule_uid].alias} · {item.status} · {item.reason}"
                    for item in conformance.context_judgments
                ),
            ),
        )
    sections = tuple(sections_list)
    metrics = [
        ResolutionMetric("SOURCE MEMORIES", str(len(session.source.memories))),
        ResolutionMetric("REDUNDANCIES", str(counts["duplicates"])),
        ResolutionMetric("AMBIGUITIES", str(counts["ambiguities"])),
        ResolutionMetric("CONFLICTS", str(counts["conflicts"])),
    ]
    if conformance is not None:
        metrics.append(
            ResolutionMetric("CONFORMANCE ISSUES", str(conformance.issue_count))
        )
    return ResolutionWorkbenchView(
        operation="AUDIT",
        artifact_uid=session.uid,
        revision=session.snapshot_digest,
        title="MEM AUDIT",
        route=session.source.context_name,
        status=f"SAVED · {check_total}/{check_total} CHECKS · READ-ONLY REPORT",
        metrics=tuple(metrics),
        context_locations=(
            ResolutionContextLocation("AUDITED SOURCE", session.source.context_name),
        ),
        overview=resolution_overview_text(sections),
        overview_sections=sections,
        list_label=(
            "AUDIT CHECKS · REDUNDANCIES → AMBIGUITIES → CONFLICTS"
            + (" · CONFORMANCE IN OVERVIEW" if conformance is not None else "")
        ),
        items=tuple(items),
        empty_message=(
            f"All {check_total} checks completed with no actionable quality findings."
        ),
        results_label="EXACT RESULTS",
        results=(),
        capabilities=frozenset(),
        show_results=False,
    )


__all__ = ["quality_audit_resolution_view"]
