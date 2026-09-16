"""Compact reusable editor for exact-versus-descendant Context reach."""

from __future__ import annotations

import sys

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
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.reach import (
    ContextReachState,
    render_context_reach,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.frame import build_focused_frame
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)


def choose_context_reach(
    *,
    title: str,
    detail: str,
    include_descendants: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> bool | None:
    """Return shared Context reach, or ``None`` when cancelled."""

    if not isinstance(title, str) or not title.strip():
        raise ValueError("Context reach title must be nonempty text.")
    if not isinstance(detail, str) or not detail.strip():
        raise ValueError("Context reach detail must be nonempty text.")
    if type(include_descendants) is not bool:
        raise TypeError("Initial Context reach must be boolean.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Context reach requires a terminal.")

    state = ContextReachState.create(include_descendants=include_descendants)
    bindings = KeyBindings()
    control = FormattedTextControl(
        lambda: render_context_reach(
            state,
            focused=get_app().layout.has_focus(control),
            title="CONTEXT RANGE",
        ),
        focusable=True,
        show_cursor=False,
    )

    def move(delta: int, event) -> None:
        state.move(delta)
        event.app.invalidate()

    @bindings.add("left", eager=True)
    def _left(event) -> None:
        move(-1, event)

    @bindings.add("right", eager=True)
    def _right(event) -> None:
        move(1, event)

    @bindings.add("enter", eager=True)
    @bindings.add(" ", eager=True)
    def _accept(event) -> None:
        event.app.exit(result=state.include_descendants)

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(
            " " + safe_terminal_text(title) + "\n " + safe_terminal_text(detail)
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    frame = build_focused_frame(
        Window(control, height=Dimension.exact(1), wrap_lines=False),
        title="RANGE · ENTER TO CONTINUE",
        is_focused=lambda: get_app().layout.has_focus(control),
        height=Dimension.exact(3),
    )
    footer = Window(
        FormattedTextControl(" ←/→ select · Enter continue · Esc cancel"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[bool | None] = Application(
        layout=Layout(HSplit([header, frame, footer]), focused_element=control),
        key_bindings=bindings,
        full_screen=False,
        mouse_support=False,
        style=MEMCOMMIT_TUI_STYLE,
        input=app_input,
        output=app_output,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
