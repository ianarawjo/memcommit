"""Typed semantic-document projection for one read-only quality finding."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.quality_find_report import QualityFindingReportItem


def _inline(value: str) -> str:
    """Collapse provider prose to one safe terminal paragraph."""

    return " ".join(safe_terminal_text(value).split())


def quality_finding_compact_fragments(
    item: QualityFindingReportItem,
    *,
    focused: bool = False,
) -> list[tuple[str, str]]:
    """Render one complete finding as a single source-linked paragraph."""

    focus_style = "class:memcommit.table.selected" if focused else ""

    def styled(base: str) -> str:
        # Focus is a transient interaction state and therefore overrides the
        # semantic Memory/report foregrounds across this one paragraph.
        return focus_style or base

    fragments: list[tuple[str, str]] = [
        (
            styled("class:report-label"),
            f"{_inline(item.kind)} · {_inline(item.classification)} — ",
        )
    ]
    for index, source in enumerate(item.sources):
        if index:
            fragments.append((styled("class:report-neutral"), " / "))
        fragments.extend(
            [
                (
                    styled("class:report-label"),
                    f"{_inline(source.label)} · {_inline(source.context_name)} "
                    f"[{_inline(source.memory_uid[:8])}]: ",
                ),
                (
                    styled("class:memory-object"),
                    f"“{_inline(source.content)}”",
                ),
            ]
        )
    fragments.extend(
        [
            (styled("class:report-neutral"), " · "),
            (
                styled("class:report-label"),
                f"{_inline(item.reason_heading)} · ",
            ),
            (styled("class:viewer-body"), _inline(item.reason)),
        ]
    )
    if item.follow_up:
        fragments.extend(
            [
                (styled("class:report-neutral"), " · "),
                (styled("class:report-label"), "QUESTION · "),
                (styled("class:viewer-body"), _inline(item.follow_up)),
            ]
        )
    if item.readings:
        fragments.extend(
            [
                (styled("class:report-neutral"), " · "),
                (styled("class:report-label"), "READINGS · "),
            ]
        )
        for index, reading in enumerate(item.readings):
            if index:
                fragments.append((styled("class:report-neutral"), " / "))
            fragments.extend(
                [
                    (
                        styled("class:report-label"),
                        f"{_inline(reading.label)}: ",
                    ),
                    (styled("class:viewer-body"), _inline(reading.text)),
                ]
            )
    fragments.append((styled("class:report-neutral"), "\n"))
    return fragments


def quality_finding_compact_text(item: QualityFindingReportItem) -> str:
    """Return the ANSI-free equivalent of the compact finding paragraph."""

    return "".join(text for _style, text in quality_finding_compact_fragments(item))


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
    "quality_finding_compact_fragments",
    "quality_finding_compact_text",
    "quality_finding_item_document",
    "quality_finding_item_sections",
]
