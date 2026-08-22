"""Typed semantic-document projection for one read-only quality finding."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.quality_find_report import QualityFindingReportItem


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


__all__ = ["quality_finding_item_document", "quality_finding_item_sections"]
