"""Interactive exact-name editor for a newly initialized Study run."""

from __future__ import annotations

import sys

from prompt_toolkit import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.widgets import Dialog, Frame, Label, TextArea

from memcommit.commands.tui_primitives import MEMCOMMIT_TUI_STYLE, display_escape_text
from memcommit.profile_config import ProfileConfigError, validate_profile_name


STUDY_NAME_STYLE = merge_styles(
    [
        MEMCOMMIT_TUI_STYLE,
        Style.from_dict(
            {
                "study-name-field frame.border": "fg:#8bd5ff",
                "study-name-field frame.label": "fg:#8bd5ff bold",
                "study-name-input": "fg:#cad3f5 bg:#24273a",
                "error": "fg:#ed8796 bold",
            }
        ),
    ]
)


def choose_study_profile_name(
    default_name: str,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Return an exact edited Profile name, or ``None`` when cancelled."""
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Study naming requires a terminal.")

    status = {"value": ""}
    bindings = KeyBindings()
    name_input = TextArea(
        text=default_name,
        multiline=False,
        prompt="",
        height=1,
        style="class:study-name-input",
        name="study-profile-name",
    )
    # TextArea initializes a prefilled buffer at column zero. Study names are
    # normally edited at the unique suffix, so start the visible caret at the
    # end while preserving ordinary Left/Right and deletion behavior.
    name_input.buffer.cursor_position = len(default_name)

    def submit(event) -> None:
        try:
            selected = validate_profile_name(name_input.text)
        except (ProfileConfigError, ValueError) as error:
            status["value"] = display_escape_text(str(error))
            event.app.invalidate()
            return
        event.app.exit(result=selected)

    @bindings.add("enter", filter=has_focus(name_input), eager=True)
    def _submit(event) -> None:
        submit(event)

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def render_status() -> FormattedText:
        if status["value"]:
            return FormattedText([("class:error", status["value"])])
        return FormattedText(
            [("", "Edit directly · Ctrl-U clear · Enter create · Esc cancel")]
        )

    name_frame = Frame(
        name_input,
        title="EDIT NAME",
        style="class:study-name-field",
        height=Dimension.exact(3),
    )

    body = HSplit(
        [
            Label("Study Profile name", dont_extend_height=True),
            name_frame,
            Window(
                FormattedTextControl(render_status),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
        ],
        padding=1,
    )
    dialog = Dialog(
        title="NEW STUDY",
        body=body,
        width=Dimension(min=48, preferred=72, max=88),
        with_background=True,
    )
    app: Application[str | None] = Application(
        layout=Layout(dialog, focused_element=name_input),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=True,
        style=STUDY_NAME_STYLE,
        input=app_input,
        output=app_output,
    )
    return app.run()
