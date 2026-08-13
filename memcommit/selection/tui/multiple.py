"""Terminal rows for operation-neutral flat multiple selection."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.core.theme import focused_control_style
from memcommit.interfaces.tui.core.text_layout import (
    terminal_cell_width,
    wrap_terminal_text,
)
from memcommit.selection.state import FlatMultiSelectionState
from memcommit.selection.tui.rendering import choice_marker


def render_vertical_multi_choice_rows(
    state: FlatMultiSelectionState,
    *,
    focused: bool,
    content_width: int,
    numbered: bool = True,
    anchor_cursor: bool = True,
) -> list[tuple[str, str]]:
    """Render a checked flat result set without implying single selection."""

    width = max(12, content_width)
    fragments: list[tuple[str, str]] = []
    for index, option in enumerate(state.options, start=1):
        cursor = option.uid == state.cursor_uid
        selected = option.uid in state.selected_uids
        keyboard_target = cursor and focused
        label_style = focused_control_style(
            focused=keyboard_target,
            selected=selected or keyboard_target,
        )
        description_style = focused_control_style(
            focused=keyboard_target,
            selected=selected or keyboard_target,
        )
        prefix = f"{choice_marker(selected=selected)} "
        if numbered:
            prefix += f"{index}. "
        label_width = max(1, width - terminal_cell_width(prefix))
        label_lines = tuple(
            wrap_terminal_text(safe_terminal_text(option.label), label_width)
        )
        fragments.append((label_style, prefix + label_lines[0] + "\n"))
        continuation = " " * terminal_cell_width(prefix)
        fragments.extend(
            (label_style, continuation + line + "\n") for line in label_lines[1:]
        )
        if option.description:
            description_prefix = "  "
            description_width = max(
                1,
                width - terminal_cell_width(description_prefix),
            )
            fragments.extend(
                (description_style, description_prefix + line + "\n")
                for line in wrap_terminal_text(
                    safe_terminal_text(option.description),
                    description_width,
                )
            )
        if keyboard_target and anchor_cursor:
            fragments.append(("[SetCursorPosition]", ""))
        if index < len(state.options):
            fragments.append(("", "\n"))
    return fragments


__all__ = ["render_vertical_multi_choice_rows"]
