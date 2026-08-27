"""Reusable full-screen dialog for one fixed flat selection."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.frame import build_focused_frame
from memcommit.interfaces.tui.core.keybindings import bind_case_insensitive_key
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.console.selection import FlatSelectionState, SelectionOption
from memcommit.interfaces.console.selection.tui import render_vertical_choice_rows


def choose_flat_option(
    options: Sequence[SelectionOption],
    *,
    title: str,
    detail: str,
    footer_note: str = "",
    initial_uid: str | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SelectionOption | None:
    """Return one checked option without assigning operation semantics."""

    frozen = tuple(options)
    if not frozen:
        raise ValueError("Selection requires at least one option.")
    if any(not isinstance(option, SelectionOption) for option in frozen):
        raise TypeError("Selection received an invalid option.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Selection title must be nonempty text.")
    if not isinstance(detail, str) or not detail.strip():
        raise ValueError("Selection detail must be nonempty text.")
    if not isinstance(footer_note, str):
        raise TypeError("Selection footer note must be text.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive selection requires a terminal.")

    initial = initial_uid or frozen[0].uid
    state = FlatSelectionState(
        frozen,
        cursor_uid=initial,
        selected_uid=initial,
        allow_empty=False,
    )
    bindings = KeyBindings()

    def render_options() -> list[tuple[str, str]]:
        width = max(30, get_app().output.get_size().columns - 8)
        return render_vertical_choice_rows(
            state,
            focused=get_app().layout.has_focus(control),
            content_width=width,
            numbered=False,
        )

    control = FormattedTextControl(
        render_options,
        focusable=True,
        show_cursor=False,
    )

    def move(delta: int, event) -> None:
        if state.move(delta):
            state.select_cursor(toggle=False)
        event.app.invalidate()

    @bindings.add("down", eager=True)
    def _down(event) -> None:
        move(1, event)

    @bindings.add("up", eager=True)
    def _up(event) -> None:
        move(-1, event)

    @bindings.add("enter", eager=True)
    @bindings.add(" ", eager=True)
    def _accept(event) -> None:
        selected_uid = state.select_cursor(toggle=False)
        event.app.exit(
            result=next(option for option in frozen if option.uid == selected_uid)
        )

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(
            [
                ("class:report-label", " " + safe_terminal_text(title) + "\n"),
                ("class:report-neutral", " " + safe_terminal_text(detail)),
            ]
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    frame = build_focused_frame(
        options_window,
        title="OPTIONS · ENTER TO CONTINUE",
        is_focused=lambda: get_app().layout.has_focus(control),
    )
    footer_text = " ↑/↓ move · Enter select · Esc/Q cancel"
    if footer_note.strip():
        footer_text += " · " + safe_terminal_text(footer_note)
    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[SelectionOption | None] = Application(
        layout=Layout(HSplit([header, frame, footer]), focused_element=control),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        input=app_input,
        output=app_output,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
