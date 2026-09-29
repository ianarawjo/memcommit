"""Shared checked-card grammar for horizontal and vertical choice layouts."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    focused_control_style,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
    wrap_terminal_fragments,
)
from memcommit.adapters.console.terminal.components.selection.state import (
    FlatSelectionState,
)


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
    lines: tuple[str | tuple[tuple[str, str], ...], ...],
    *,
    visual: ChoiceVisualState,
    width: int | None = None,
    title: str | None = None,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Render one Meld-style rectangle as rows of styled fragments."""

    if not lines:
        raise ValueError("A choice card requires visible content.")
    body_style = "" if title is not None else visual.content_style
    safe_lines = tuple(
        tuple(
            (style, safe_terminal_text(text).replace("\n", "↵"))
            for style, text in (
                ((body_style, line),) if isinstance(line, str) else line
            )
        )
        for line in lines
    )
    widths = tuple(
        sum(terminal_cell_width(text) for _, text in line) for line in safe_lines
    )
    content_width = max(1, max(widths))
    safe_title = (
        single_line_terminal_text(safe_terminal_text(title))
        if title is not None
        else None
    )
    if safe_title is not None:
        content_width = max(content_width, terminal_cell_width(safe_title) + 3)
    if width is not None:
        if width < (6 if title is not None else 3):
            raise ValueError("A choice card width must leave room for its border.")
        content_width = width - 2
        if any(line_width > content_width for line_width in widths):
            raise ValueError("Choice card content exceeds its requested width.")
    horizontal = "━" if visual.keyboard_target else "─"
    vertical = "┃" if visual.keyboard_target else "│"
    top = "┏" if visual.keyboard_target else "┌"
    top_right = "┓" if visual.keyboard_target else "┐"
    bottom = "┗" if visual.keyboard_target else "└"
    bottom_right = "┛" if visual.keyboard_target else "┘"
    if title is None:
        top_row = ((visual.border_style, top + horizontal * content_width + top_right),)
    else:
        label = elide_terminal_text(safe_title, max(1, content_width - 3))
        remaining = max(0, content_width - terminal_cell_width(label) - 3)
        top_row = (
            (visual.border_style, top + horizontal + " "),
            (visual.content_style, label),
            (visual.border_style, " " + horizontal * remaining + top_right),
        )
    rows: list[tuple[tuple[str, str], ...]] = [top_row]
    # A border title carries the choice state; keep its evidence readable.
    for line, line_width in zip(safe_lines, widths, strict=True):
        padding = max(0, content_width - line_width)
        rows.append(
            (
                (visual.border_style, vertical),
                *line,
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
    label_in_border: bool = False,
    descriptions: Mapping[str, tuple[tuple[str, str], ...]] | None = None,
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
        title = prefix.strip() + " " + option.label if label_in_border else None
        lines = [] if label_in_border else [prefix + label_lines[0]]
        continuation = " " * terminal_cell_width(prefix)
        if not label_in_border:
            lines.extend(continuation + line for line in label_lines[1:])
        rich_description = (descriptions or {}).get(option.uid)
        if rich_description is not None:
            safe_description = tuple(
                (style, safe_terminal_text(text).replace("\t", "    "))
                for style, text in rich_description
            )
            lines.extend(
                (("", "  "), *line)
                for line in wrap_terminal_fragments(safe_description, inner_width - 2)
            )
        elif option.description:
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
            tuple(lines) or ("",),
            visual=visual,
            width=width,
            title=title.strip() if title is not None else None,
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
