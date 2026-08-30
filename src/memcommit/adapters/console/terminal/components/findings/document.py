"""Typed semantic-document projection for one read-only quality issue."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.report import (
    QualityFindReportView,
    QualityFindingReportItem,
    quality_find_category_label,
    quality_find_report_summary_text,
)


def _inline(value: str) -> str:
    """Collapse provider prose to one safe terminal paragraph."""

    return " ".join(safe_terminal_text(value).split())


def quality_find_report_header_text(
    view: QualityFindReportView,
    *,
    label: str | None = None,
) -> str:
    """Return the one-line finder summary shared by Find and saved Audit."""

    resolved_label = (
        quality_find_category_label(view.kind) if label is None else _inline(label)
    )
    return (
        f"{resolved_label} · {quality_find_report_summary_text(view)} · "
        f"[SOURCE {_inline(view.route)}]"
    )


def quality_finding_item_sections(
    item: QualityFindingReportItem,
    *,
    uid_prefix: str = "",
) -> tuple[SemanticViewerSection, ...]:
    """Project complete source-linked finding evidence without answer controls."""

    prefix = f"{uid_prefix}FINDING:{item.uid}"
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            f"{prefix}:IDENTITY",
            "IDENTITY",
            SemanticViewerBlock(
                (
                    (
                        "class:report-label",
                        f" {safe_terminal_text(item.kind)} · "
                        f"{safe_terminal_text(item.classification)}\n",
                    ),
                    (
                        "class:memory-object",
                        f" {safe_terminal_text(item.title)}\n",
                    ),
                )
            ),
        )
    ]
    for source in item.sources:
        sections.append(
            SemanticViewerSection(
                f"{prefix}:SOURCE:{source.memory_uid}",
                "SOURCE",
                SemanticViewerBlock(
                    (
                        (
                            "class:report-label",
                            f" {safe_terminal_text(source.label)} · "
                            f"{safe_terminal_text(source.context_name)} · "
                            f"[{safe_terminal_text(source.memory_uid[:8])}]\n",
                        ),
                        (
                            "class:memory-object",
                            f" {safe_terminal_text(source.content)}\n",
                        ),
                    )
                ),
            )
        )
    sections.append(
        SemanticViewerSection(
            f"{prefix}:REASON",
            "REASON",
            SemanticViewerBlock(
                (
                    (
                        "class:report-label",
                        f" {safe_terminal_text(item.reason_heading)}\n",
                    ),
                    (
                        "class:viewer-body",
                        f" {safe_terminal_text(item.reason)}\n",
                    ),
                )
            ),
        )
    )
    if item.follow_up:
        sections.append(
            SemanticViewerSection(
                f"{prefix}:FOLLOW_UP",
                "FOLLOW_UP",
                SemanticViewerBlock(
                    (
                        ("class:report-label", " FOLLOW-UP QUESTION\n"),
                        (
                            "class:viewer-body",
                            f" {safe_terminal_text(item.follow_up)}\n",
                        ),
                    )
                ),
            )
        )
    if item.readings:
        fragments: list[tuple[str, str]] = [
            ("class:report-label", " POSSIBLE READINGS\n")
        ]
        for reading in item.readings:
            fragments.extend(
                [
                    (
                        "class:report-neutral",
                        f" - {safe_terminal_text(reading.label)} · ",
                    ),
                    (
                        "class:viewer-body",
                        safe_terminal_text(reading.text) + "\n",
                    ),
                ]
            )
        sections.append(
            SemanticViewerSection(
                f"{prefix}:READINGS",
                "READINGS",
                SemanticViewerBlock(tuple(fragments)),
            )
        )
    return tuple(sections)


def quality_finding_item_document(
    item: QualityFindingReportItem,
) -> SemanticViewerDocument:
    """Return a standalone document for the compact finding browser."""

    return SemanticViewerDocument(quality_finding_item_sections(item))


__all__ = [
    "quality_find_report_header_text",
    "quality_finding_item_document",
    "quality_finding_item_sections",
]
