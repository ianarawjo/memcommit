"""Pure History row and detail presentation; no application or operation state."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.adapters.console.terminal.components.history.model import (
    HistoryPickerItem,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    semantic_action_style,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.text_layout import (
    AdaptiveColumn,
    allocate_adaptive_columns,
    elide_terminal_text,
    pad_terminal_text,
    terminal_cell_width,
)


VISIBLE_ROWS = 12


def visible_history_bounds(selected: int, count: int) -> tuple[int, int]:
    visible = min(count, VISIBLE_ROWS)
    start = max(0, selected - visible // 2)
    start = min(start, count - visible)
    return start, start + visible


def detail_unit_position(unit_start_lines: tuple[int, ...], row: int) -> int:
    """Map a logical Viewer row to its one-based semantic change position."""

    if not unit_start_lines:
        raise ValueError("Detail position requires at least one unit anchor.")
    return max(1, bisect_right(unit_start_lines, max(0, row)))


def _compact_timestamp(value: str) -> str:
    return display_escape_text(value[:16].replace("T", " "))


def _compact(value: str, width: int) -> str:
    return elide_terminal_text(display_escape_text(value), width)


def _entry_line_parts(
    entry: HistoryPickerItem,
    *,
    entries: Sequence[HistoryPickerItem],
    selected: bool,
    checked: bool = False,
    available_width: int,
) -> tuple[str, str, str, str]:
    """Lay out one History row before presentation styles are applied."""

    pointer = "›" if selected else " "
    marker = "✓" if checked else " "
    timestamp = (
        f"{_compact_timestamp(entry.timestamp):<16}  " if available_width >= 58 else ""
    )
    uid = display_escape_text(entry.uid)[:8]
    prefix = f"{pointer}{marker} {timestamp}"
    suffix = f"  {uid}  "
    field_budget = max(
        0,
        available_width - terminal_cell_width(prefix + suffix),
    )
    commands = tuple(display_escape_text(item.command) for item in entries)
    descriptions = tuple(
        display_escape_text(item.description or "(no description)") for item in entries
    )
    command_natural = max(
        (terminal_cell_width(value) for value in commands),
        default=0,
    )
    description_natural = max(
        (terminal_cell_width(value) for value in descriptions),
        default=0,
    )
    widths = allocate_adaptive_columns(
        field_budget,
        (
            AdaptiveColumn(
                "command",
                minimum=min(6, command_natural),
                preferred=command_natural,
                maximum=command_natural,
                shrink_order=1,
                grow_order=0,
            ),
            AdaptiveColumn(
                "description",
                minimum=min(10, description_natural),
                preferred=description_natural,
                shrink_order=0,
                grow_order=1,
                expand=True,
            ),
        ),
    )
    command = pad_terminal_text(
        elide_terminal_text(display_escape_text(entry.command), widths["command"]),
        widths["command"],
    )
    description = elide_terminal_text(
        display_escape_text(entry.description or "(no description)"),
        widths["description"],
    )
    return prefix, command, suffix, description


def _render_entry_line(
    entry: HistoryPickerItem,
    *,
    entries: Sequence[HistoryPickerItem],
    selected: bool,
    checked: bool = False,
    available_width: int,
) -> str:
    """Render the stable plain projection of one History Items row."""

    return elide_terminal_text(
        "".join(
            _entry_line_parts(
                entry,
                entries=entries,
                selected=selected,
                checked=checked,
                available_width=available_width,
            )
        ),
        available_width,
    )


def render_history_entry_fragments(
    entry: HistoryPickerItem,
    *,
    entries: Sequence[HistoryPickerItem],
    selected: bool,
    checked: bool = False,
    available_width: int,
) -> StyleAndTextTuples:
    """Color only the action token; keyboard focus still owns the whole row."""

    parts = _entry_line_parts(
        entry,
        entries=entries,
        selected=selected,
        checked=checked,
        available_width=available_width,
    )
    rendered = "".join(parts)
    focused_style = "class:memcommit.table.selected" if selected else ""
    if terminal_cell_width(rendered) > available_width:
        return [(focused_style, elide_terminal_text(rendered, available_width))]
    prefix, command, suffix, description = parts
    return [
        (focused_style, prefix),
        (
            focused_style
            or semantic_action_style(entry.command, fallback="class:report-neutral"),
            command,
        ),
        (focused_style, suffix + description),
    ]


def _indented_detail(value: str) -> tuple[str, ...]:
    """Keep item content visibly subordinate to the trusted metadata labels."""
    # Only explicit LF characters retain layout meaning. Tabs, carriage
    # returns, bidi controls, Unicode separators, and backslashes remain
    # visible escapes so item content cannot imitate the trusted frame.
    lines = tuple(
        display_escape_text(line) for line in (value or "(no detail)").split("\n")
    )
    return (
        f" Detail       {lines[0]}",
        *(f"              {line}" for line in lines[1:]),
    )


def render_history_detail(entry: HistoryPickerItem) -> str:
    """Render the complete selected record through a single-line trust boundary."""
    description = entry.description or "(no description)"
    return "\n".join(
        (
            f" UID          {display_escape_text(entry.uid)}",
            f" Time         {display_escape_text(entry.timestamp)}",
            f" Command      {display_escape_text(entry.command)}",
            f" Description  {display_escape_text(description)}",
            *_indented_detail(entry.detail),
        )
    )
