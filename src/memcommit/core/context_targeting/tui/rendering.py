"""Shared row grammar for Context namespace trees."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.adapters.interfaces.console.text import (
    display_escape_text,
)
from memcommit.core.context_targeting.tui.tree import ContextTreeRow, ContextTreeState
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    SourceTokenRole,
    normalize_source_display_tokens,
)
from memcommit.source_projection.tui import render_source_display_tokens


@dataclass(frozen=True)
class ContextTreeRowDecoration:
    """Operation-supplied semantics around one shared namespace row grammar."""

    marker: str = ""
    active: str = ""
    annotation: SourceDisplayValue | None = None
    value_suffix: str = ""
    cursor_style: str = ""
    value_style: str | None = None
    branch: str | None = None
    nested_fragments: tuple[tuple[str, str], ...] = ()
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
        branch = decoration.branch or (
            "▾" if row.expanded else "▸" if row.has_children else "·"
        )
        prefix = (
            f"{pointer} {decoration.marker} {decoration.active} "
            f"{'  ' * row.depth}{branch} "
        )
        value = f"{display_escape_text(row.name)}{display_escape_text(decoration.value_suffix)}"
        display_tokens = normalize_source_display_tokens(decoration.annotation)
        ownership_tokens = tuple(
            token for token in display_tokens if token.role is SourceTokenRole.OWNERSHIP
        )
        annotation_tokens = tuple(
            token
            for token in display_tokens
            if token.role is not SourceTokenRole.OWNERSHIP
        )
        if decoration.value_style is None:
            if ownership_tokens:
                fragments.append((decoration.cursor_style, prefix))
                fragments.extend(
                    render_source_display_tokens(
                        ownership_tokens,
                        override_style=decoration.cursor_style,
                    )
                )
                fragments.append((decoration.cursor_style, " " + value))
            else:
                fragments.append((decoration.cursor_style, prefix + value))
            annotation_style = decoration.cursor_style
        else:
            fragments.append((decoration.cursor_style, prefix))
            if ownership_tokens:
                fragments.extend(render_source_display_tokens(ownership_tokens))
                fragments.append((decoration.cursor_style, " "))
            fragments.append((decoration.value_style, value))
            annotation_style = decoration.value_style
        if annotation_tokens:
            fragments.append((annotation_style, "  "))
            fragments.extend(
                render_source_display_tokens(
                    annotation_tokens,
                    override_style=annotation_style,
                )
            )
        fragments.extend(decoration.nested_fragments)
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments
