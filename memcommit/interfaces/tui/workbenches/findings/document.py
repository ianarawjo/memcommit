"""Typed semantic-document projection for one read-only quality finding."""

from __future__ import annotations

from memcommit.interfaces.console.identity import collision_safe_uid_prefixes
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    semantic_quality_role,
)
from memcommit.interfaces.tui.core.theme import semantic_role_style
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.quality_find_report import (
    QualityFindReportView,
    QualityFindingReportItem,
)


def _inline(value: str) -> str:
    """Collapse provider prose to one safe terminal paragraph."""

    return " ".join(safe_terminal_text(value).split())


def quality_finding_compact_fragments(
    item: QualityFindingReportItem,
    *,
    focused: bool = False,
    show_context: bool = True,
) -> list[tuple[str, str]]:
    """Render one issue as one source-linked logical line.

    The Context and Memory identifiers deliberately use separate typed
    brackets.  ``context@uid`` is not a public reference grammar and becomes
    ambiguous as soon as a Context name itself needs escaping.
    """

    focus_style = "class:memcommit.table.selected" if focused else ""

    def styled(base: str) -> str:
        # Focus is a transient interaction state and therefore overrides the
        # semantic Memory/report foregrounds across this one paragraph.
        return focus_style or base

    role = semantic_quality_role(item.category)
    if role is None:  # pragma: no cover - the typed report validates the union.
        raise ValueError("Unsupported quality finding category.")
    if item.category == "ambiguities":
        marker, finding_label = "?", "AMBIGUOUS"
        classification = ""
    elif item.category == "conflicts":
        marker, finding_label = "!", "CONFLICT"
        parts = [part.strip() for part in item.classification.split("·")]
        classification = " · ".join(
            part for part in parts if part.upper() not in {"YES", "MAY", "NO"}
        )
    elif item.classification == "EXACT":
        marker, finding_label = "=", "DUPLICATE"
        classification = item.classification
    else:
        marker, finding_label = "≈", "REDUNDANT"
        classification = item.classification

    fragments: list[tuple[str, str]] = [
        (styled("class:report-neutral"), f"{marker} "),
        (styled(semantic_role_style(role)), finding_label),
    ]
    if classification:
        fragments.extend(
            [
                (styled("class:report-neutral"), " · "),
                (styled("class:report-label"), _inline(classification)),
            ]
        )
    fragments.append((styled("class:report-neutral"), " · "))
    uid_prefixes = collision_safe_uid_prefixes(
        source.memory_uid for source in item.sources
    )
    for index, source in enumerate(item.sources):
        if index:
            fragments.append((styled("class:report-neutral"), " ↔ "))
        if show_context:
            fragments.extend(
                [
                    (
                        styled("class:report-label"),
                        f"[CONTEXT {_inline(source.context_name)}] ",
                    ),
                ]
            )
        fragments.extend(
            [
                (
                    styled("class:report-label"),
                    f"[MEMORY {_inline(uid_prefixes[source.memory_uid])}] ",
                ),
                (styled("class:memory-object"), f"“{_inline(source.content)}”"),
            ]
        )

    # Redundancy is understandable from the relation and exact pair alone.
    # Ambiguity keeps possible readings, but folds them into the rationale
    # instead of presenting answer-looking numbered choices or a question.
    if item.category != "duplicates":
        rationale = _inline(item.reason)
        if item.category == "ambiguities" and item.readings:
            readings = " / ".join(_inline(reading.text) for reading in item.readings)
            rationale = f"{rationale.rstrip()} — {readings}"
        fragments.extend(
            [
                (styled("class:report-neutral"), " · "),
                (
                    styled(semantic_role_style(SemanticColorRole.RATIONALE)),
                    "WHY",
                ),
                (styled("class:report-neutral"), " · "),
                (styled("class:viewer-body"), rationale),
            ]
        )
    fragments.append((styled("class:report-neutral"), "\n"))
    return fragments


def quality_finding_compact_text(
    item: QualityFindingReportItem,
    *,
    show_context: bool = True,
) -> str:
    """Return the ANSI-free equivalent of the compact finding paragraph."""

    return "".join(
        text
        for _style, text in quality_finding_compact_fragments(
            item,
            show_context=show_context,
        )
    )


def quality_find_report_header_text(
    view: QualityFindReportView,
    *,
    label: str | None = None,
) -> str:
    """Return the one-line finder summary shared by Find and saved Audit."""

    resolved_label = (
        {
            "ambiguities": "AMBIGUITIES",
            "conflicts": "CONFLICTS",
            "duplicates": "REDUNDANCIES",
        }[view.kind]
        if label is None
        else _inline(label)
    )
    return (
        f"{resolved_label} · {len(view.items)}/{view.candidate_count} "
        f"{view.candidate_unit} FLAGGED · [SOURCE {_inline(view.route)}]"
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
    "quality_finding_compact_fragments",
    "quality_finding_compact_text",
    "quality_find_report_header_text",
    "quality_finding_item_document",
    "quality_finding_item_sections",
]
