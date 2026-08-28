"""Shared checked-card grammar for horizontal and vertical choice layouts."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.adapters.console.tui.core.theme import (
    focused_control_style,
)
from memcommit.adapters.console.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.tui.core.text_layout import (
    terminal_cell_width,
    wrap_terminal_text,
)
from memcommit.adapters.console.selection.state import FlatSelectionState


@dataclass(frozen=True)
class ChoiceVisualState:
    """One layout-independent cursor and checked presentation decision."""

    cursor: bool
    selected: bool
    control_focused: bool

    @property
    def keyboard_target(self) -> bool:
        return self.cursor and self.control_focused

    @property
    def border_style(self) -> str:
        return "class:memcommit.choice.border.focused" if self.keyboard_target else ""

    @property
    def content_style(self) -> str:
        return focused_control_style(
            focused=self.keyboard_target,
            selected=self.selected,
        )


def choice_visual_state(
    *,
    cursor: bool,
    selected: bool,
    focused: bool,
) -> ChoiceVisualState:
    return ChoiceVisualState(cursor, selected, focused)


def choice_marker(*, selected: bool, empty: str = " ") -> str:
    """Use one checked marker policy without radio circles or diamonds."""

    return "✓" if selected else empty


def tree_choice_marker(*, selected: bool, available: bool = True) -> str:
    """Project the checked policy into the compact fixed-width tree slot."""

    if not available:
        return "×"
    return choice_marker(selected=selected, empty="·")


def tree_choice_styles(
    *,
    cursor: bool,
    selected: bool,
    focused: bool,
) -> tuple[str, str]:
    """Keep tree geometry while sharing checked and focus color semantics."""

    cursor_focused = cursor and focused
    cursor_style = "class:memcommit.table.selected" if cursor_focused else ""
    visual = choice_visual_state(
        cursor=cursor,
        selected=selected,
        focused=focused,
    )
    return cursor_style, visual.content_style if selected else cursor_style


def render_choice_card_rows(
    lines: tuple[str, ...],
    *,
    visual: ChoiceVisualState,
    width: int | None = None,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Render one Meld-style rectangle as rows of styled fragments."""

    if not lines:
        raise ValueError("A choice card requires visible content.")
    safe_lines = tuple(
        safe_terminal_text(line)
        .replace("\r\n", "↵")
        .replace("\r", "↵")
        .replace("\n", "↵")
        for line in lines
    )
    content_width = max(1, max(terminal_cell_width(line) for line in safe_lines))
    if width is not None:
        if width < 3:
            raise ValueError("A choice card width must leave room for its border.")
        content_width = width - 2
        if any(terminal_cell_width(line) > content_width for line in safe_lines):
            raise ValueError("Choice card content exceeds its requested width.")
    horizontal = "━" if visual.keyboard_target else "─"
    vertical = "┃" if visual.keyboard_target else "│"
    top = "┏" if visual.keyboard_target else "┌"
    top_right = "┓" if visual.keyboard_target else "┐"
    bottom = "┗" if visual.keyboard_target else "└"
    bottom_right = "┛" if visual.keyboard_target else "┘"
    rows: list[tuple[tuple[str, str], ...]] = [
        ((visual.border_style, top + horizontal * content_width + top_right),)
    ]
    for line in safe_lines:
        padding = max(0, content_width - terminal_cell_width(line))
        rows.append(
            (
                (visual.border_style, vertical),
                (visual.content_style, line),
                ("", " " * padding),
                (visual.border_style, vertical),
            )
        )
    rows.append(
        ((visual.border_style, bottom + horizontal * content_width + bottom_right),)
    )
    return tuple(rows)


def render_vertical_choice_cards(
    state: FlatSelectionState,
    *,
    focused: bool,
    content_width: int,
    numbered: bool = True,
    anchor_cursor: bool = True,
    indent: str = "",
) -> list[tuple[str, str]]:
    """Render long choices as stacked cards through the Meld rectangle policy."""

    width = max(12, content_width)
    inner_width = width - 2
    fragments: list[tuple[str, str]] = []
    for index, option in enumerate(state.options, start=1):
        cursor = option.uid == state.cursor_uid
        selected = option.uid == state.selected_uid
        visual = choice_visual_state(
            cursor=cursor,
            selected=selected,
            focused=focused,
        )
        prefix = f"{choice_marker(selected=selected)} "
        if numbered:
            prefix += f"{index}. "
        label_width = max(1, inner_width - terminal_cell_width(prefix))
        label_lines = tuple(
            wrap_terminal_text(safe_terminal_text(option.label), label_width)
        )
        lines = [prefix + label_lines[0]]
        continuation = " " * terminal_cell_width(prefix)
        lines.extend(continuation + line for line in label_lines[1:])
        if option.description:
            description_prefix = "  "
            description_width = max(
                1,
                inner_width - terminal_cell_width(description_prefix),
            )
            lines.extend(
                description_prefix + line
                for line in wrap_terminal_text(
                    safe_terminal_text(option.description),
                    description_width,
                )
            )
        rows = render_choice_card_rows(
            tuple(lines),
            visual=visual,
            width=width,
        )
        for row in rows:
            if indent:
                fragments.append(("", indent))
            fragments.extend(row)
            fragments.append(("", "\n"))
        if visual.keyboard_target and anchor_cursor:
            # Anchor after the closing border so scrolling reveals the whole
            # focused card instead of leaving only its top edge at the bottom.
            fragments.append(("[SetCursorPosition]", ""))
        if index < len(state.options):
            fragments.append(("", "\n"))
    return fragments

def render_vertical_choice_rows(
    state: FlatSelectionState,
    *,
    focused: bool,
    content_width: int,
    numbered: bool = True,
    anchor_cursor: bool = True,
    blank_between: bool = True,
) -> list[tuple[str, str]]:
    """Render stacked choices as highlighted text rows without card chrome.

    The label is bold at the keyboard target, while the wrapped description
    keeps the same highlight without bold. This preserves one visible focus
    region without turning explanatory prose into a second heading.
    """

    width = max(12, content_width)
    fragments: list[tuple[str, str]] = []
    for index, option in enumerate(state.options, start=1):
        cursor = option.uid == state.cursor_uid
        selected = option.uid == state.selected_uid
        keyboard_target = cursor and focused
        highlighted = selected or keyboard_target
        label_style = focused_control_style(
            focused=keyboard_target,
            selected=highlighted,
        )
        description_style = focused_control_style(
            focused=False,
            selected=highlighted,
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
        if blank_between and index < len(state.options):
            fragments.append(("", "\n"))
    return fragments
