"""Comprehensive read-only Viewer projection for one saved quality Audit."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
    ViewerAnchor,
    semantic_document_plain_text,
)
from memcommit.interfaces.tui.workbenches.findings import (
    quality_finding_item_sections,
)
from memcommit.quality_audit import (
    QualityAuditSession,
    quality_audit_resolution_view,
)
from memcommit.quality_find_workbench import (
    QualityFindSourceFrame,
    QualityFindWorkbenchSession,
    quality_find_report_view,
    quality_find_resolution_view,
)


def _report_section(
    uid: str,
    kind: str,
    heading: str,
    text: str,
    *,
    anchor: ViewerAnchor = "start",
) -> SemanticViewerSection:
    return SemanticViewerSection(
        uid,
        kind,
        SemanticViewerBlock(
            (
                ("class:report-label", f" {safe_terminal_text(heading)}\n"),
                ("class:viewer-body", f" {safe_terminal_text(text)}\n"),
            ),
            anchor=anchor,
        ),
    )


def quality_audit_review_document(
    session: QualityAuditSession,
) -> SemanticViewerDocument:
    """Project the complete saved Audit without editable review mechanics."""

    if not isinstance(session, QualityAuditSession):
        raise TypeError("Audit Review requires one typed saved Audit.")
    compatibility_view = quality_audit_resolution_view(session)
    overview_by_uid = {
        section.uid: section for section in compatibility_view.overview_sections
    }
    check_total = 4 if session.conformance is not None else 3
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            "AUDIT:HEADER",
            "HEADER",
            SemanticViewerBlock(
                (
                    ("class:report-label", " MEM AUDIT\n"),
                    (
                        "class:viewer-body",
                        f" SAVED · {check_total}/{check_total} CHECKS · "
                        "READ-ONLY REPORT\n",
                    ),
                    (
                        "class:report-neutral",
                        f" SESSION [{safe_terminal_text(session.uid[:8])}] · "
                        f"CREATED {safe_terminal_text(session.created_at)} · "
                        f"{session.finding_count} FINDING(S)\n",
                    ),
                )
            ),
        )
    ]
    for uid, kind in (
        ("summary", "SUMMARY"),
        ("checks", "CHECKS"),
        ("scope", "SCOPE"),
    ):
        overview = overview_by_uid[uid]
        sections.append(
            _report_section(
                f"AUDIT:{uid.upper()}",
                kind,
                overview.heading,
                overview.text,
            )
        )

    for ordinal, memory in enumerate(session.source.memories, start=1):
        sections.append(
            SemanticViewerSection(
                f"AUDIT:SOURCE:{memory.uid}",
                "SOURCE_MEMORY",
                SemanticViewerBlock(
                    (
                        (
                            "class:report-label",
                            f" SOURCE MEMORY {ordinal}/{len(session.source.memories)} "
                            f"· [{safe_terminal_text(memory.uid[:8])}]\n",
                        ),
                        (
                            "class:memory-object",
                            f" {safe_terminal_text(memory.content)}\n",
                        ),
                    )
                ),
            )
        )

    if "conformance" in overview_by_uid:
        overview = overview_by_uid["conformance"]
        sections.append(
            _report_section(
                "AUDIT:CONFORMANCE",
                "CONFORMANCE",
                overview.heading,
                overview.text,
            )
        )
    provenance = overview_by_uid["provenance"]
    sections.append(
        _report_section(
            "AUDIT:PROVENANCE",
            "PROVENANCE",
            provenance.heading,
            provenance.text,
        )
    )

    context = session.source.context()
    source_frame = QualityFindSourceFrame.create((context,))
    for check in session.checks:
        sub_session = QualityFindWorkbenchSession(
            uid=session.uid,
            kind=check.kind,
            source=source_frame,
            report=check.report,
            responses=session.responses,
        )
        report_view = quality_find_report_view(
            sub_session,
            context,
            operation_label=f"AUDIT · {check.kind.upper()}",
        )
        count = len(report_view.items)
        sections.append(
            _report_section(
                f"AUDIT:CHECK:{check.kind}",
                "CHECK",
                f"{check.kind.upper()} · COMPLETE · {count} "
                f"{'FINDING' if count == 1 else 'FINDINGS'}",
                (
                    report_view.empty_message
                    if count == 0
                    else "Complete source-linked findings follow."
                ),
            )
        )
        legacy_items = {
            item.uid: item
            for item in quality_find_resolution_view(sub_session, context).items
        }
        for item in report_view.items:
            sections.extend(
                quality_finding_item_sections(
                    item,
                    uid_prefix=f"AUDIT:{check.kind.upper()}:",
                )
            )
            response = session.responses.get(item.uid)
            if response is None or not response.answered:
                continue
            fragments: list[tuple[str, str]] = [
                ("class:report-label", " SAVED REVIEW NOTE · HISTORICAL\n")
            ]
            if response.selected_option_uid is not None:
                option = legacy_items[item.uid].option(response.selected_option_uid)
                fragments.extend(
                    [
                        (
                            "class:report-neutral",
                            f" DISPOSITION · {safe_terminal_text(option.label)}\n",
                        ),
                        (
                            "class:viewer-body",
                            f" {safe_terminal_text(option.text)}\n",
                        ),
                    ]
                )
            if response.text.strip():
                fragments.extend(
                    [
                        ("class:report-neutral", " NOTE\n"),
                        (
                            "class:viewer-body",
                            f" {safe_terminal_text(response.text)}\n",
                        ),
                    ]
                )
            sections.append(
                SemanticViewerSection(
                    f"AUDIT:NOTE:{item.uid}",
                    "SAVED_NOTE",
                    SemanticViewerBlock(tuple(fragments)),
                )
            )

    boundary = overview_by_uid["boundary"]
    sections.append(
        _report_section(
            "AUDIT:BOUNDARY",
            "BOUNDARY",
            boundary.heading,
            (
                boundary.text
                + " This Viewer cannot select a reading, write a response, rerun a "
                "finder, or apply a Memory change."
            ),
            anchor="end",
        )
    )
    return SemanticViewerDocument(tuple(sections))


def render_quality_audit_review_snapshot(session: QualityAuditSession) -> str:
    """Render the same complete document used by interactive Audit Review."""

    document = quality_audit_review_document(session)
    return semantic_document_plain_text(
        document,
        focused_uid=None,
        whole_document=True,
    ).rstrip()


__all__ = [
    "quality_audit_review_document",
    "render_quality_audit_review_snapshot",
]
