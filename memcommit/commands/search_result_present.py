"""Shared grouping and neutral text presentation for ranked search results."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from memcommit.commands.tui_primitives import safe_terminal_text


T = TypeVar("T")


@dataclass(frozen=True)
class SearchResultViewRow:
    context_name: str
    label: str
    content: str


@dataclass(frozen=True)
class SearchResultGroup:
    context_name: str
    rows: tuple[SearchResultViewRow, ...]


def group_search_items(
    items: Sequence[T],
    *,
    context_name: Callable[[T], str],
) -> tuple[tuple[str, tuple[T, ...]], ...]:
    """Group in first-owner order while preserving ranking inside each owner."""

    grouped: dict[str, list[T]] = {}
    for item in items:
        grouped.setdefault(context_name(item), []).append(item)
    return tuple((name, tuple(values)) for name, values in grouped.items())


def group_search_result_rows(
    rows: Sequence[SearchResultViewRow],
) -> tuple[SearchResultGroup, ...]:
    return tuple(
        SearchResultGroup(name, values)
        for name, values in group_search_items(
            rows,
            context_name=lambda row: row.context_name,
        )
    )


def render_grouped_search_results(
    rows: Sequence[SearchResultViewRow],
    *,
    related_query: str = "",
    empty_message: str = "(no matching items)",
) -> str:
    """Render one common primary/related header and Context-grouped result body."""

    if not rows:
        return f"SEARCH RESULTS\n  {safe_terminal_text(empty_message)}"
    lines: list[str] = []
    if related_query:
        lines.extend(
            [
                "PRIMARY MATCHES",
                "  (none)",
                "",
                "RELATED RESULTS",
                "  Broader search: " + safe_terminal_text(related_query),
                "  Related items do not satisfy the original query.",
                "",
            ]
        )
    else:
        lines.append("SEARCH RESULTS")
    for group_index, group in enumerate(group_search_result_rows(rows)):
        if group_index:
            lines.append("")
        lines.append(safe_terminal_text(group.context_name))
        for row in group.rows:
            label = safe_terminal_text(row.label)
            content_lines = safe_terminal_text(row.content).splitlines() or [""]
            lines.append(f"  {label} {content_lines[0]}")
            indent = " " * (len(label) + 3)
            lines.extend(f"{indent}{line}" for line in content_lines[1:])
    return "\n".join(lines)
