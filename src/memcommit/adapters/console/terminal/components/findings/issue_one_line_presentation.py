"""One-logical-line presentation for one source-linked semantic issue."""

from __future__ import annotations

from collections.abc import Mapping

import typer

from memcommit.adapters.console.terminal.core.identity import (
    collision_safe_uid_prefixes,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    semantic_role_style,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    memory_object_color_rgb,
    semantic_color_rgb,
    semantic_quality_role,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.report import (
    QualityFindingReportItem,
    quality_finding_label_parts,
)


def _inline(value: str) -> str:
    """Collapse untrusted prose without truncating its logical content."""

    return " ".join(safe_terminal_text(value).split())


def issue_one_line_fragments(
    item: QualityFindingReportItem,
    *,
    focused: bool = False,
    show_context: bool = True,
    uid_prefixes: Mapping[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Present one issue as exactly one source-linked logical line.

    A narrow viewport may wrap the line visually, but the presentation never
    inserts an internal newline or truncates Memory or rationale content. The
    Context and Memory identifiers deliberately use separate typed brackets.
    """

    focus_style = "class:memcommit.table.selected" if focused else ""

    def styled(base: str) -> str:
        # Focus temporarily overrides semantic foregrounds across the complete
        # logical row so one control never appears doubly focused.
        return focus_style or base

    role = semantic_quality_role(item.category)
    if role is None:  # pragma: no cover - the typed report validates the union.
        raise ValueError("Unsupported quality issue category.")
    marker, issue_label, classification = quality_finding_label_parts(item)

    fragments: list[tuple[str, str]] = [
        (styled("class:report-neutral"), f"{marker} "),
        (styled(semantic_role_style(role)), issue_label),
    ]
    if classification:
        fragments.extend(
            [
                (styled("class:report-neutral"), " · "),
                (styled("class:report-label"), _inline(classification)),
            ]
        )
    fragments.append((styled("class:report-neutral"), " · "))
    prefixes = (
        collision_safe_uid_prefixes(source.memory_uid for source in item.sources)
        if uid_prefixes is None
        else uid_prefixes
    )
    if any(source.memory_uid not in prefixes for source in item.sources):
        raise ValueError("Issue presentation is missing a Source Memory prefix.")
    for index, source in enumerate(item.sources):
        if index:
            fragments.append((styled("class:report-neutral"), " ↔ "))
        if show_context:
            fragments.append(
                (
                    styled("class:report-label"),
                    f"[CONTEXT {_inline(source.context_name)}] ",
                )
            )
        fragments.extend(
            [
                (
                    styled("class:report-label"),
                    f"[MEMORY {_inline(prefixes[source.memory_uid])}] ",
                ),
                (styled("class:memory-object"), f"“{_inline(source.content)}”"),
            ]
        )

    # Redundancy is understandable from the relation and exact pair alone.
    # Ambiguity keeps possible readings, but folds them into the rationale
    # instead of presenting answer-looking numbered choices.
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
    if item.follow_up:
        fragments.extend(
            [
                (styled("class:report-neutral"), " · "),
                (styled("class:report-label"), "QUESTION"),
                (styled("class:report-neutral"), " · "),
                (styled("class:viewer-body"), _inline(item.follow_up)),
            ]
        )
    fragments.append((styled("class:report-neutral"), "\n"))
    return fragments


def issue_one_line_text(
    item: QualityFindingReportItem,
    *,
    show_context: bool = True,
    uid_prefixes: Mapping[str, str] | None = None,
) -> str:
    """Return the ANSI-free equivalent of one issue-line presentation."""

    return "".join(
        text
        for _style, text in issue_one_line_fragments(
            item,
            show_context=show_context,
            uid_prefixes=uid_prefixes,
        )
    )


def echo_issue_one_line(
    item: QualityFindingReportItem,
    *,
    prefix: str = "",
    show_context: bool = True,
    uid_prefixes: Mapping[str, str] | None = None,
) -> None:
    """Render the same presentation through the line-oriented CLI adapter."""

    if prefix:
        typer.echo(prefix, nl=False)
    for style, value in issue_one_line_fragments(
        item,
        show_context=show_context,
        uid_prefixes=uid_prefixes,
    ):
        if style == "class:memory-object":
            typer.secho(value, fg=memory_object_color_rgb(), nl=False)
        elif style == "class:report-label":
            typer.secho(value, bold=True, nl=False)
        elif style.startswith("class:semantic."):
            role = SemanticColorRole(style.removeprefix("class:semantic."))
            typer.secho(value, fg=semantic_color_rgb(role), bold=True, nl=False)
        else:
            typer.echo(value, nl=False)


__all__ = [
    "echo_issue_one_line",
    "issue_one_line_fragments",
    "issue_one_line_text",
]
