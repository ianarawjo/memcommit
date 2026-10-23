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

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.frame import build_focused_frame
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.components.selection import (
    SingleSelectionState,
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.selection import (
    render_vertical_choice_rows,
)


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
    compact: bool = False,
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

    initial = initial_uid or frozen[0].value
    state = SingleSelectionState(
        frozen,
        cursor_value=initial,
        selected_value=initial,
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
            blank_between=not compact,
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
        selected_value = state.select_cursor(toggle=False)
        event.app.exit(
            result=next(option for option in frozen if option.value == selected_value)
        )

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(
            [
                (
                    "class:report-neutral",
                    " " + safe_terminal_text(title) + " " + safe_terminal_text(detail),
                )
            ]
            if compact
            else [
                ("class:report-label", " " + safe_terminal_text(title) + "\n"),
                ("class:report-neutral", " " + safe_terminal_text(detail)),
            ]
        ),
        height=Dimension.exact(1 if compact else 2),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=True,
        right_margins=[] if compact else [ScrollbarMargin(display_arrows=True)],
        height=Dimension.exact(len(frozen)) if compact else None,
    )
    frame = (
        options_window
        if compact
        else build_focused_frame(
            options_window,
            title="OPTIONS · ENTER TO CONTINUE",
            is_focused=lambda: get_app().layout.has_focus(control),
        )
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
        full_screen=not compact,
        erase_when_done=compact,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        input=app_input,
        output=app_output,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
