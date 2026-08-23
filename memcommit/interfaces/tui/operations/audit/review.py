"""Comprehensive read-only Viewer projection for one saved quality Audit."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.console.theme import semantic_quality_role
from memcommit.interfaces.tui.core.theme import semantic_role_style
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
    ViewerAnchor,
    semantic_document_plain_text,
)
from memcommit.interfaces.tui.workbenches.findings import (
    quality_finding_compact_fragments,
    quality_find_report_header_text,
)
from memcommit.quality_audit import (
    QualityAuditSession,
    quality_audit_resolution_view,
)
from memcommit.quality_find_workbench import (
    QualityFindSourceFrame,
    QualityFindWorkbenchSession,
    quality_find_report_view,
)


def _inline(value: str) -> str:
    return " ".join(safe_terminal_text(value).split())


def _inline_lines(value: str) -> str:
    return " / ".join(
        compact
        for line in safe_terminal_text(value).splitlines()
        if (compact := " ".join(line.split()))
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
                ("class:viewer-body", f" {_inline_lines(text)}\n"),
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
    counts = {
        check.kind: len(check.report.findings) for check in session.checks
    }
    overview_fragments: list[tuple[str, str]] = [
        ("class:report-label", " MEM AUDIT\n"),
        (
            "class:viewer-body",
            f" SAVED · {check_total}/{check_total} CHECKS · READ-ONLY REPORT\n",
        ),
        (
            "class:report-neutral",
            f" SESSION [{safe_terminal_text(session.uid[:8])}] · "
            f"CREATED {safe_terminal_text(session.created_at)} · "
            f"{session.finding_count} FINDING(S)\n",
        ),
        ("class:report-label", " SUMMARY · "),
        ("class:viewer-body", _inline(overview_by_uid["summary"].text) + "\n"),
        ("class:report-label", " CHECKS · "),
        (
            "class:viewer-body",
            _inline_lines(overview_by_uid["checks"].text) + "\n",
        ),
        ("class:report-label", " SOURCE · "),
        ("class:viewer-body", _inline(overview_by_uid["scope"].text) + "\n"),
        ("class:report-label", " SNAPSHOT · "),
    ]
    for ordinal, memory in enumerate(session.source.memories):
        if ordinal:
            overview_fragments.append(("class:report-neutral", " / "))
        overview_fragments.extend(
            [
                (
                    "class:report-label",
                    f"[{safe_terminal_text(memory.uid[:8])}] ",
                ),
                ("class:memory-object", _inline(memory.content)),
            ]
        )
    overview_fragments.append(("class:report-neutral", "\n"))

    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            "AUDIT:OVERVIEW",
            "OVERVIEW",
            SemanticViewerBlock(tuple(overview_fragments)),
        )
    ]

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
        count = counts[check.kind]
        header_label = check.kind.upper()
        header_text = quality_find_report_header_text(
            report_view,
            label=header_label,
        )
        header_role = semantic_quality_role(check.kind)
        if header_role is None:  # pragma: no cover - Audit validates this union.
            raise ValueError("Unsupported Audit quality check kind.")
        fragments: list[tuple[str, str]] = [
            ("class:report-neutral", " "),
            (semantic_role_style(header_role), header_label),
            ("class:report-label", header_text[len(header_label) :] + "\n"),
        ]
        if count == 0:
            fragments.append(
                ("class:viewer-body", f" {_inline(report_view.empty_message)}\n")
            )
        for item in report_view.items:
            fragments.append(("class:report-neutral", " "))
            fragments.extend(
                quality_finding_compact_fragments(
                    item,
                    show_context=report_view.source_count > 1,
                )
            )
        sections.append(
            SemanticViewerSection(
                f"AUDIT:CHECK:{check.kind}",
                "CHECK",
                SemanticViewerBlock(tuple(fragments)),
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
