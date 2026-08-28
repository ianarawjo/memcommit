"""Terminal projection for an ordered direct-item gap control."""

from __future__ import annotations

import textwrap

from prompt_toolkit.utils import get_cwidth

from memcommit.core.context_targeting.tui.tree import ContextTreeRow
from memcommit.adapters.console.text import display_escape_text
from memcommit.adapters.console.tui.components.direct_item_placement.model import (
    DirectItemGapState,
    DirectItemPreview,
)
from memcommit.adapters.console.selection.tui import tree_choice_marker, tree_choice_styles
from memcommit.source_projection.presentation import (
    source_annotation_tokens,
    source_object_label,
)
from memcommit.source_projection.tui import render_source_display_tokens


def _gap_label(state: DirectItemGapState, position: int) -> str:
    gap_count = len(state.rows) + 1
    if not state.rows:
        return "FIRST = LAST · DEFAULT · 1/1"
    if position == 0:
        return f"FIRST · 1/{gap_count}"
    if position == len(state.rows):
        return f"LAST · DEFAULT · {gap_count}/{gap_count}"
    return f"POSITION · {position + 1}/{gap_count}"


def _render_position_line(
    state: DirectItemGapState,
    *,
    row: ContextTreeRow,
    editing: bool,
    focused: bool,
    width: int,
) -> list[tuple[str, str]]:
    position = state.cursor_position if editing else state.selected_position
    selected = position == state.selected_position
    cursor_style, value_style = tree_choice_styles(
        cursor=editing,
        selected=selected,
        focused=focused,
    )
    indent = "  " * (row.depth + 1)
    pointer = "›" if editing else " "
    marker = tree_choice_marker(selected=selected)
    prefix = f"{indent}{pointer} {marker} ───────── "
    label = _gap_label(state, position)
    fill = "─" * max(1, width - get_cwidth(prefix) - get_cwidth(label) - 1)
    fragments: list[tuple[str, str]] = [("", "\n")]
    if editing:
        fragments.append(("[SetCursorPosition]", ""))
    fragments.extend(
        (
            (cursor_style, prefix),
            (value_style, label),
            (cursor_style, " " + fill),
        )
    )
    return fragments


def _render_preview(
    row: ContextTreeRow,
    preview: DirectItemPreview,
    *,
    width: int,
) -> list[tuple[str, str]]:
    style = f"class:{preview.style}"
    object_label = source_object_label(preview.source)
    leading = (
        "  " * (row.depth + 1)
        + f"· [{display_escape_text(object_label)} "
        + f"{display_escape_text(preview.label)}] "
    )
    annotations = source_annotation_tokens(preview.source)
    annotation_text = " · ".join(token.text for token in annotations)
    annotation_width = get_cwidth(annotation_text + (" · " if annotations else ""))
    content_width = max(1, width - get_cwidth(leading) - annotation_width)
    content_lines = textwrap.wrap(
        display_escape_text(preview.content),
        width=content_width,
        replace_whitespace=False,
        drop_whitespace=False,
    ) or [""]
    fragments: list[tuple[str, str]] = [("", "\n"), (style, leading)]
    if annotations:
        fragments.extend(render_source_display_tokens(annotations))
        fragments.append((style, " · "))
    fragments.append((style, content_lines[0]))
    continuation_indent = " " * (get_cwidth(leading) + annotation_width)
    for continuation in content_lines[1:]:
        fragments.extend((("", "\n"), (style, continuation_indent + continuation)))
    return fragments


def render_direct_item_tree_fragments(
    state: DirectItemGapState,
    *,
    row: ContextTreeRow,
    editing: bool,
    focused: bool,
    width: int,
) -> list[tuple[str, str]]:
    """Render fixed item rows around one visible insertion line."""

    available_width = max(24, width)
    fragments: list[tuple[str, str]] = []
    visible_position = state.cursor_position if editing else state.selected_position
    for position in range(len(state.rows) + 1):
        if position == visible_position:
            fragments.extend(
                _render_position_line(
                    state,
                    row=row,
                    editing=editing,
                    focused=focused,
                    width=available_width,
                )
            )
        if position < len(state.rows):
            fragments.extend(
                _render_preview(
                    row,
                    state.rows[position].preview,
                    width=available_width,
                )
            )
    return fragments
