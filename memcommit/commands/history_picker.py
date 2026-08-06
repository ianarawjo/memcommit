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
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    display_escape_text,
)


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
    escaped = display_escape_text(value)
    if len(escaped) <= width:
        return escaped
    return escaped[: max(0, width - 1)] + "…"


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
) -> HistorySelectionReceipt | None:
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
        fragments: list[tuple[str, str]] = []
        for index in range(start, end):
            entry = options[index]
            selected = index == state.selected_index
            if selected:
                fragments.append(("[SetCursorPosition]", ""))
            pointer = "›" if selected else " "
            command = _compact(entry.command, 12)
            description = _compact(
                entry.description or "(no description)",
                58,
            )
            fragments.append(
                (
                    "class:memcommit.table.selected" if selected else "",
                    (
                        f"{pointer} {_compact_timestamp(entry.timestamp):<16}  "
                        f"{command:<12}  "
                        f"{display_escape_text(entry.uid)[:8]}  {description}"
                    ),
                )
            )
            if index < end - 1:
                fragments.append(("", "\n"))
        return fragments

    def render_detail() -> str | StyleAndTextTuples:
        if not options:
            return ""
        entry = options[state.selected_index]
        return (
            detail_renderer(entry)
            if detail_renderer is not None
            else _render_detail(entry)
        )

    def render_footer() -> str:
        if not options:
            return " Esc/q close  ·  0/0"
        position = f"{state.selected_index + 1}/{len(options)}"
        if mode == "revert":
            action = "Enter revert to exact UID"
            close = "Esc/q cancel"
        else:
            action = (
                "Enter hide details"
                if state.details_open
                else "Enter details"
            )
            close = "Esc/q close"
        return f" ↑/↓ move  {action}  {close}  ·  {position}"

    list_control = FormattedTextControl(
        text=render_entries,
        focusable=True,
        show_cursor=False,
    )
    detail_control = FormattedTextControl(
        text=render_detail,
        focusable=False,
        show_cursor=False,
    )

    @bindings.add("down")
    def _next_checkpoint(event) -> None:
        if not options:
            return
        _move(state, 1, len(options))
        event.app.invalidate()

    @bindings.add("up")
    def _previous_checkpoint(event) -> None:
        if not options:
            return
        _move(state, -1, len(options))
        event.app.invalidate()

    @bindings.add("enter")
    def _enter(event) -> None:
        if not options:
            return
        result = _activate(
            state,
            mode=mode,
            context_name=context_name,
            entry=options[state.selected_index],
        )
        if mode == "revert":
            event.app.exit(result=result)
        else:
            event.app.invalidate()

    @bindings.add("q", eager=True)
    @bindings.add("escape", eager=True)
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
    options_window = Window(
        list_control,
        height=Dimension(
            min=1,
            preferred=min(len(options), _VISIBLE_ROWS),
            max=_VISIBLE_ROWS,
        ),
        wrap_lines=False,
    )
    detail_window = ConditionalContainer(
        Window(
            detail_control,
            height=Dimension(min=6, preferred=10, weight=1),
            wrap_lines=True,
        ),
        filter=Condition(lambda: state.details_open),
    )
    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[HistorySelectionReceipt | None] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    Window(height=1, char="─"),
                    options_window,
                    Window(height=1, char="─"),
                    detail_window,
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
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
