"""Shared row grammar for Context namespace trees."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.context_targeting.tui.tree import ContextTreeRow, ContextTreeState


@dataclass(frozen=True)
class ContextTreeRowDecoration:
    """Operation-supplied semantics around one shared namespace row grammar."""

    marker: str = ""
    active: str = ""
    annotation: str = ""
    cursor_style: str = ""
    value_style: str | None = None
    anchor_cursor: bool = True
    show_cursor: bool = True


ContextTreeRowDecorator = Callable[[ContextTreeRow, bool], ContextTreeRowDecoration]


def render_context_tree_rows(
    state: ContextTreeState,
    decorate: ContextTreeRowDecorator,
) -> list[tuple[str, str]]:
    """Render pointer, marker slots, indentation, branch, name, and line breaks.

    Operations supply marker meaning, availability annotation, and styles but
    cannot drift the common namespace geometry or terminal escaping policy.
    """

    fragments: list[tuple[str, str]] = []
    rows = state.visible_rows()
    for index, row in enumerate(rows):
        cursor = row.name == state.selected_name
        decoration = decorate(row, cursor)
        if cursor and decoration.show_cursor and decoration.anchor_cursor:
            fragments.append(("[SetCursorPosition]", ""))
        pointer = "›" if cursor and decoration.show_cursor else " "
        branch = "▾" if row.expanded else "▸" if row.has_children else "·"
        prefix = (
            f"{pointer} {decoration.marker} {decoration.active} "
            f"{'  ' * row.depth}{branch} "
        )
        suffix = (
            f"  {display_escape_text(decoration.annotation)}"
            if decoration.annotation
            else ""
        )
        value = f"{display_escape_text(row.name)}{suffix}"
        if decoration.value_style is None:
            fragments.append((decoration.cursor_style, prefix + value))
        else:
            fragments.extend(
                (
                    (decoration.cursor_style, prefix),
                    (decoration.value_style, value),
                )
            )
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments
