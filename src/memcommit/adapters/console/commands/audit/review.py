"""Comprehensive read-only Viewer projection for one saved quality Audit."""

from __future__ import annotations

import sys

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
import typer

from memcommit.adapters.console.commands.audit.session_catalog import (
    audit_session_entries,
)
from memcommit.adapters.console.commands.review.sessions import select_report_session
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.theme import semantic_quality_role
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    semantic_role_style,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
    ViewerAnchor,
    run_semantic_viewer,
    semantic_document_plain_text,
)
from memcommit.adapters.console.terminal.components.findings import (
    issue_one_line_fragments,
    quality_find_report_header_text,
)
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.audit.session_store import QualityAuditStore
from memcommit.application.capabilities.reviewing.memory_issue_finding.report import (
    QualityFindReportView,
    quality_find_category_label,
    quality_find_report_summary_text,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.workbench import (
    QualityFindSourceFrame,
    QualityFindWorkbenchSession,
    quality_find_report_view,
)
from memcommit.persistence.store import MemoryStore


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
    context = session.source.context()
    source_frame = QualityFindSourceFrame.create((context,))
    report_views: dict[str, QualityFindReportView] = {}
    for check in session.checks:
        label = quality_find_category_label(check.kind)
        report_views[check.kind] = quality_find_report_view(
            QualityFindWorkbenchSession(
                uid=session.uid,
                kind=check.kind,
                source=source_frame,
                report=check.report,
            ),
            context,
            operation_label=f"AUDIT · {label}",
        )

    check_total = 4 if session.conformance is not None else 3
    summary_text = (
        "All Memory-issue finders completed over the same saved direct Context "
        "snapshot. Each section retains its own Memory, pair, group, or "
        "absorption unit."
    )
    if session.conformance is not None:
        summary_text += (
            " Conformance evaluated the same Source against "
            f"{len(session.conformance.rules)} frozen Rules."
        )
    checks_text = "\n".join(
        f"{quality_find_category_label(check.kind)} · FINISHED · "
        f"{quality_find_report_summary_text(report_views[check.kind])}"
        for check in session.checks
    )
    if session.conformance is not None:
        checks_text += (
            "\nCONFORMANCE · FINISHED · "
            f"{len(session.conformance.context_judgments)} Rules · "
            f"{session.conformance.issue_count} issues"
        )
    source_text = (
        f"{session.source.context_name} · {len(session.source.memories)} direct "
        "Memories as captured when this Audit ran. Descendants and embedded "
        "Contexts were not analyzed."
    )
    overview_fragments: list[tuple[str, str]] = [
        ("class:report-label", " MEM AUDIT\n"),
        (
            "class:viewer-body",
            f" SAVED · {check_total}/{check_total} CHECKS · READ-ONLY REPORT\n",
        ),
        (
            "class:report-neutral",
            f" SESSION [{safe_terminal_text(session.uid[:8])}] · "
            f"CREATED {safe_terminal_text(session.created_at)}\n",
        ),
        ("class:report-label", " SUMMARY · "),
        ("class:viewer-body", _inline(summary_text) + "\n"),
        ("class:report-label", " CHECKS · "),
        ("class:viewer-body", _inline_lines(checks_text) + "\n"),
        ("class:report-label", " SOURCE · "),
        ("class:viewer-body", _inline(source_text) + "\n"),
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

    for check in session.checks:
        header_label = quality_find_category_label(check.kind)
        report_view = report_views[check.kind]
        count = len(check.report.findings)
        header_text = quality_find_report_header_text(
            report_view,
            label=header_label,
        )
        header_role = semantic_quality_role(check.kind)
        if header_role is None:  # pragma: no cover - Audit validates this union.
            raise ValueError("Unsupported Audit quality check kind.")
        header_fragments: list[tuple[str, str]] = [
            ("class:report-neutral", " "),
            (semantic_role_style(header_role), header_label),
            ("class:report-label", header_text[len(header_label) :] + "\n"),
        ]
        if count == 0:
            header_fragments.append(
                ("class:viewer-body", f" {_inline(report_view.empty_message)}\n")
            )
        sections.append(
            SemanticViewerSection(
                f"AUDIT:CHECK:{check.kind}",
                "CHECK",
                SemanticViewerBlock(tuple(header_fragments)),
            )
        )
        for item in report_view.items:
            # A finder can return many findings.  Keep each source-linked
            # paragraph as one semantic stop so one large category cannot
            # become an indivisible Viewer scroll block.
            finding_fragments = [("class:report-neutral", " ")]
            compact_fragments = issue_one_line_fragments(
                item,
                show_context=report_view.source_count > 1,
            )
            # The compact projector begins with the typed =/≈/?/! marker and
            # its category label.  The marker changes color at focus; the
            # label keeps semantic color and gains emphasis only at focus.
            marker_style, marker_text = compact_fragments[0]
            if marker_style != "class:report-neutral":  # pragma: no cover
                raise ValueError("Audit finding marker projection changed.")
            compact_fragments[0] = ("class:finding-marker", marker_text)
            label_style, label_text = compact_fragments[1]
            if label_style != semantic_role_style(header_role):  # pragma: no cover
                raise ValueError("Audit finding label projection changed.")
            compact_fragments[1] = (
                f"{label_style} class:finding-label",
                label_text,
            )
            finding_fragments.extend(compact_fragments)
            sections.append(
                SemanticViewerSection(
                    f"AUDIT:CHECK:{check.kind}:FINDING:{item.uid}",
                    "FINDING",
                    SemanticViewerBlock(tuple(finding_fragments)),
                )
            )

    conformance = session.conformance
    if conformance is not None:
        rule_by_uid = {rule.uid: rule for rule in conformance.rules}
        sections.append(
            _report_section(
                "AUDIT:CONFORMANCE",
                "CONFORMANCE",
                "CONFORMANCE",
                "\n".join(
                    f"{rule_by_uid[item.rule_uid].alias} · {item.status} · {item.reason}"
                    for item in conformance.context_judgments
                ),
            )
        )
    provenance_lines = [
        f"{quality_find_category_label(check.kind)} · {check.ruleset_version} · "
        f"{check.provenance.display_name()}"
        for check in session.checks
    ]
    if conformance is not None:
        identity = conformance.provider_identity
        assert identity is not None
        provenance_lines.append(
            f"CONFORMANCE · {conformance.ruleset_version} · {identity.display_name()}"
        )
    sections.append(
        _report_section(
            "AUDIT:PROVENANCE",
            "PROVENANCE",
            "PROVENANCE",
            "\n".join(provenance_lines),
        )
    )

    sections.append(
        _report_section(
            "AUDIT:BOUNDARY",
            "BOUNDARY",
            "BOUNDARY",
            (
                "This saved Audit is a model-assisted finding record, not proof "
                "that the Source is free of Memory issues. This Viewer cannot "
                "select a reading, write a response, rerun a finder, or apply a "
                "Memory change."
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


def run_quality_audit_review(
    store: MemoryStore,
    session: QualityAuditSession,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> QualityAuditSession:
    """Read one complete saved Audit without rerunning or editing it."""

    # Keep the Store parameter for the established command adapter signature,
    # but do not open it: the already validated saved snapshot is the review
    # object and this Viewer owns no persistence boundary.
    del store
    run_semantic_viewer(
        quality_audit_review_document(session),
        title="AUDIT REVIEW",
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    return session


def open_audit_review(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    """Open one exact saved Audit without rerunning any finder."""

    sessions = QualityAuditStore(store)
    selected = select_report_session(
        audit_session_entries(sessions),
        kind="audit",
        title="MEM REVIEW · AUDIT REPORTS",
        session_uid=session_uid,
    )
    if selected is None:
        return
    session = sessions.load(selected.key)
    if snapshot or not (sys.stdin.isatty() and sys.stdout.isatty()):
        typer.echo(render_quality_audit_review_snapshot(session))
        return
    run_quality_audit_review(store, session)


__all__ = [
    "open_audit_review",
    "quality_audit_review_document",
    "render_quality_audit_review_snapshot",
    "run_quality_audit_review",
]
