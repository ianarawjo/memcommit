"""Shared terminal picker for inspecting or selecting temporal history items.

The picker deliberately receives presentation summaries rather than store
objects.  History reconstruction, semantic search, freshness validation, and
the eventual revert remain responsibilities of their command adapters.
"""
from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable, Literal, Protocol, runtime_checkable

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.widgets import Frame

from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    bind_focused_frame_style,
    display_escape_text,
)
from memcommit.commands.tui_text_layout import (
    AdaptiveColumn,
    allocate_adaptive_columns,
    elide_terminal_text,
    live_window_content_width,
    pad_terminal_text,
    terminal_cell_width,
)
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation


HistoryPickerMode = Literal["log", "revert"]
_VISIBLE_ROWS = 12


@runtime_checkable
class HistoryPickerItem(Protocol):
    """Minimal projection a checkpoint or temporal Find adapter must provide."""

    uid: str
    timestamp: str
    command: str
    description: str
    detail: str


@dataclass(frozen=True)
class HistoryPickerEntry:
    """Validated built-in implementation of :class:`HistoryPickerItem`."""

    uid: str
    timestamp: str
    command: str
    description: str
    detail: str

    def __post_init__(self) -> None:
        for label, value in (
            ("history UID", self.uid),
            ("history timestamp", self.timestamp),
            ("history command", self.command),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{label} must be non-empty text.")
        if not isinstance(self.description, str):
            raise ValueError("history description must be text.")
        if not isinstance(self.detail, str):
            raise ValueError("history detail must be text.")


@dataclass(frozen=True)
class HistorySelectionReceipt:
    """Exact local selection returned by the mutation-oriented picker mode."""

    context_name: str
    checkpoint_uid: str


@dataclass(frozen=True)
class HistoryBackNavigation:
    """Read-only receipt requesting return to the owning previous screen."""


HISTORY_BACK = HistoryBackNavigation()


@dataclass
class _PickerState:
    selected_index: int
    details_open: bool


def _visible_bounds(selected: int, count: int) -> tuple[int, int]:
    visible = min(count, _VISIBLE_ROWS)
    start = max(0, selected - visible // 2)
    start = min(start, count - visible)
    return start, start + visible


def _move(state: _PickerState, delta: int, count: int) -> None:
    state.selected_index = max(
        0,
        min(state.selected_index + delta, count - 1),
    )


def _activate(
    state: _PickerState,
    *,
    mode: HistoryPickerMode,
    context_name: str,
    entry: HistoryPickerItem,
) -> HistorySelectionReceipt | None:
    """Apply Enter's mode-specific behavior without touching persistent state."""
    if mode == "log":
        state.details_open = not state.details_open
        return None
    return HistorySelectionReceipt(
        context_name=context_name,
        checkpoint_uid=entry.uid,
    )


def _compact_timestamp(value: str) -> str:
    return display_escape_text(value[:16].replace("T", " "))


def _compact(value: str, width: int) -> str:
    return elide_terminal_text(display_escape_text(value), width)


def _render_entry_line(
    entry: HistoryPickerItem,
    *,
    entries: Sequence[HistoryPickerItem],
    selected: bool,
    available_width: int,
) -> str:
    """Render command and description columns from the live Items width."""

    pointer = "›" if selected else " "
    timestamp = (
        f"{_compact_timestamp(entry.timestamp):<16}  "
        if available_width >= 58
        else ""
    )
    uid = display_escape_text(entry.uid)[:8]
    prefix = f"{pointer} {timestamp}"
    suffix = f"  {uid}  "
    field_budget = max(
        0,
        available_width - terminal_cell_width(prefix + suffix),
    )
    commands = tuple(display_escape_text(item.command) for item in entries)
    descriptions = tuple(
        display_escape_text(item.description or "(no description)")
        for item in entries
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
    return elide_terminal_text(
        f"{prefix}{command}{suffix}{description}",
        available_width,
    )


def _indented_detail(value: str) -> tuple[str, ...]:
    """Keep item content visibly subordinate to the trusted metadata labels."""
    # Only explicit LF characters retain layout meaning. Tabs, carriage
    # returns, bidi controls, Unicode separators, and backslashes remain
    # visible escapes so item content cannot imitate the trusted frame.
    lines = tuple(
        display_escape_text(line)
        for line in (value or "(no detail)").split("\n")
    )
    return (
        f" Detail       {lines[0]}",
        *(f"              {line}" for line in lines[1:]),
    )


def _render_detail(entry: HistoryPickerItem) -> str:
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


def choose_history(
    entries: Sequence[HistoryPickerItem],
    *,
    context_name: str,
    mode: HistoryPickerMode,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    initial_details_open: bool | None = None,
    detail_renderer: Callable[[HistoryPickerItem], StyleAndTextTuples] | None = None,
    empty_message: str | None = None,
    back_navigation: bool = False,
) -> HistorySelectionReceipt | HistoryBackNavigation | None:
    """Inspect history or return one exact checkpoint selection.

    In ``log`` mode Enter toggles the selected checkpoint's details and only a
    close/cancel key exits.  In ``revert`` mode the details stay visible and
    Enter returns an exact UID receipt; this function never performs a revert.
    """
    options = tuple(entries)
    if not isinstance(context_name, str) or not context_name:
        raise ValueError("History selection requires a Context name.")
    if mode not in {"log", "revert"}:
        raise ValueError("History picker mode must be 'log' or 'revert'.")
    if not options and (mode != "log" or not empty_message):
        raise ValueError("No history entries are available to select.")
    if any(not isinstance(entry, HistoryPickerItem) for entry in options):
        raise ValueError("History selection received an invalid entry.")
    for entry in options:
        for value in (
            entry.uid,
            entry.timestamp,
            entry.command,
            entry.description,
            entry.detail,
        ):
            if not isinstance(value, str):
                raise ValueError(
                    "History selection received an invalid entry."
                )
    if len({entry.uid for entry in options}) != len(options):
        raise ValueError("History selection received duplicate entry UIDs.")
    if detail_renderer is not None and not callable(detail_renderer):
        raise ValueError("History detail renderer must be callable.")
    if require_tty and (
        not sys.stdin.isatty() or not sys.stdout.isatty()
    ):
        raise ValueError(
            "Interactive history selection requires a terminal. "
            "Pass a checkpoint UID explicitly or use plain log output."
        )

    state = _PickerState(
        selected_index=0,
        details_open=(
            mode == "revert"
            if initial_details_open is None
            else initial_details_open
        ),
    )
    bindings = KeyBindings()

    def render_entries() -> list[tuple[str, str]]:
        if not options:
            return [("class:report-neutral", f"  {display_escape_text(empty_message or '')}")]
        start, end = _visible_bounds(state.selected_index, len(options))
        visible = options[start:end]
        available_width = live_window_content_width(
            windows.get("items"),
            fallback_reserved=3,
        )
        fragments: list[tuple[str, str]] = []
        for index in range(start, end):
            entry = options[index]
            selected = index == state.selected_index
            if selected:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:memcommit.table.selected" if selected else "",
                    _render_entry_line(
                        entry,
                        entries=visible,
                        selected=selected,
                        available_width=available_width,
                    ),
                )
            )
            if index < end - 1:
                fragments.append(("", "\n"))
        return fragments

    def render_detail() -> str | StyleAndTextTuples:
        if not options:
            return " No checkpoint operation is available."
        if not state.details_open:
            return " Select an item and press Enter to open its detail."
        entry = options[state.selected_index]
        return (
            detail_renderer(entry)
            if detail_renderer is not None
            else _render_detail(entry)
        )

    def render_footer() -> str:
        close = (
            "Esc/Backspace back  q close"
            if back_navigation
            else "Esc/Backspace/q close"
        )
        if not options:
            return f" {close}  ·  0/0"
        position = f"{state.selected_index + 1}/{len(options)}"
        if navigation.pane == "viewer":
            return (
                " FOCUS VIEWER · ↑/↓ scroll  Enter/Esc/Backspace items  "
                f"Tab switch  q close  ·  {position}"
            )
        if mode == "revert":
            action = "Enter revert to exact UID"
            close = (
                "Esc/Backspace back  q cancel"
                if back_navigation
                else "Esc/Backspace/q cancel"
            )
        else:
            action = "Enter viewer"
        return (
            f" FOCUS ITEMS · ↑/↓ move  {action}  Tab switch  {close}"
            f"  ·  {position}"
        )

    list_control = FormattedTextControl(
        text=render_entries,
        focusable=True,
        show_cursor=False,
    )
    detail_control = FormattedTextControl(
        text=render_detail,
        focusable=True,
        show_cursor=False,
    )
    navigation = SessionWorkbenchNavigation(pane="items")
    options_window = Window(
        list_control,
        height=Dimension(
            min=1,
            preferred=min(len(options), _VISIBLE_ROWS),
            max=_VISIBLE_ROWS,
            weight=3,
        ),
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    detail_window = Window(
        detail_control,
        height=Dimension(min=6, preferred=14, weight=7),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    windows = {"viewer": detail_window, "items": options_window}

    @bindings.add("down")
    def _next_checkpoint(event) -> None:
        if navigation.pane == "viewer":
            detail_window.vertical_scroll += 1
            event.app.invalidate()
            return
        if not options:
            return
        _move(state, 1, len(options))
        detail_window.vertical_scroll = 0
        event.app.invalidate()

    @bindings.add("up")
    def _previous_checkpoint(event) -> None:
        if navigation.pane == "viewer":
            detail_window.vertical_scroll = max(
                0,
                detail_window.vertical_scroll - 1,
            )
            event.app.invalidate()
            return
        if not options:
            return
        _move(state, -1, len(options))
        detail_window.vertical_scroll = 0
        event.app.invalidate()

    @bindings.add("enter")
    def _enter(event) -> None:
        if navigation.pane == "viewer":
            navigation.focus("items")
            event.app.layout.focus(windows["items"])
            event.app.invalidate()
            return
        if not options:
            return
        if mode == "revert":
            result = _activate(
                state,
                mode=mode,
                context_name=context_name,
                entry=options[state.selected_index],
            )
            event.app.exit(result=result)
        else:
            state.details_open = True
            navigation.open_selected()
            detail_window.vertical_scroll = 0
            event.app.layout.focus(windows["viewer"])
            event.app.invalidate()

    @bindings.add("tab")
    def _next_pane(event) -> None:
        pane = navigation.toggle_frames()
        event.app.layout.focus(windows[pane])
        event.app.invalidate()

    @bindings.add("s-tab")
    def _previous_pane(event) -> None:
        pane = navigation.toggle_frames()
        event.app.layout.focus(windows[pane])
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        if navigation.pane == "viewer":
            navigation.focus("items")
            event.app.layout.focus(windows["items"])
            event.app.invalidate()
            return
        event.app.exit(result=HISTORY_BACK if back_navigation else None)

    @bindings.add("q", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(
            " "
            + ("HISTORY" if mode == "log" else "REVERT")
            + " · "
            + display_escape_text(context_name)
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    viewer_frame = Frame(detail_window, title="VIEWER")
    items_frame = Frame(options_window, title="ITEMS")
    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[
        HistorySelectionReceipt | HistoryBackNavigation | None
    ] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    viewer_frame,
                    items_frame,
                    footer,
                ]
            ),
            focused_element=list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    for pane, frame in (("viewer", viewer_frame), ("items", items_frame)):
        bind_focused_frame_style(
            frame,
            is_focused=lambda pane=pane: navigation.pane == pane,
        )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
