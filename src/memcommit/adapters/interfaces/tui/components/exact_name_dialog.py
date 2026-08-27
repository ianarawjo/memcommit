"""Compact operation-neutral editor for one exact single-line name."""

from __future__ import annotations

import sys

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import FormattedText
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

from memcommit.adapters.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.adapters.interfaces.tui.components.exact_name import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.adapters.interfaces.tui.core.theme import MEMCOMMIT_TUI_STYLE


def choose_exact_name(
    view: ExactNameFieldView,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Return one validated exact name, or ``None`` when cancelled."""

    if not isinstance(view, ExactNameFieldView):
        raise TypeError("Exact-name dialog requires an ExactNameFieldView.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive naming requires a terminal.")

    status = {"value": ""}
    bindings = KeyBindings()
    field = ExactNameFieldControl.create(
        view,
        input_name="exact-name-dialog",
        frame_title="",
    )
    field.input.buffer.cursor_position = len(view.value)

    @bindings.add("enter", filter=has_focus(field.input), eager=True)
    def _submit(event) -> None:
        try:
            selected = field.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            status["value"] = display_escape_text(str(error))
            event.app.invalidate()
            return
        event.app.exit(result=selected)

    @bindings.add("c-j", filter=has_focus(field.input), eager=True)
    def _reject_newline(event) -> None:
        status["value"] = f"{view.value_label} must stay on one line."
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def render_footer() -> FormattedText:
        if status["value"]:
            return FormattedText([("class:error", " " + status["value"])])
        return FormattedText(
            [
                (
                    "",
                    " "
                    + safe_terminal_text(view.detail)
                    + " · Ctrl-U clear · Enter continue · Esc cancel",
                )
            ]
        )

    root = HSplit(
        [
            Window(
                FormattedTextControl(
                    FormattedText([("class:heading", " " + view.label)])
                ),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            field.frame,
            Window(
                FormattedTextControl(render_footer),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
        ],
        height=Dimension.exact(5),
    )
    app: Application[str | None] = Application(
        layout=Layout(root, focused_element=field.input),
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
