"""Compact inline TUI for naming a newly initialized Study run."""

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

from memcommit.adapters.console.commands.shared.tui_primitives import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.interfaces.console.text import (
    display_escape_text,
)
from memcommit.application.operations.profile.config import ProfileConfigError, validate_profile_name


STUDY_NAME_STYLE = merge_styles(
    [
        MEMCOMMIT_TUI_STYLE,
        Style.from_dict(
            {
                "study-name-field frame.border": "fg:#8bd5ff",
                "study-name-label": "fg:#8bd5ff bold",
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
    """Return an edited name from a five-line TUI, or ``None`` on cancel."""
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Study naming requires a terminal.")

    status = {"value": ""}
    bindings = KeyBindings()
    name_field = ExactNameFieldControl.create(
        ExactNameFieldView(
            value=default_name,
            label="STUDY NAME",
            validate=validate_profile_name,
            value_label="Study Profile name",
            # Profile validation intentionally sees whitespace exactly as
            # typed; unlike CLI destination names, it is not prompt padding.
            strip_candidate=False,
        ),
        input_name="study-profile-name",
        prompt="",
        input_style="class:study-name-input",
        frame_style="class:study-name-field",
        frame_title="",
    )
    name_input = name_field.input
    # The compact editor is primarily for replacing or refining the generated
    # suffix, so expose a real caret at the end without selecting the value.
    name_input.buffer.cursor_position = len(default_name)

    @bindings.add("enter", filter=has_focus(name_input), eager=True)
    def _submit(event) -> None:
        try:
            selected = name_field.validate_candidate()
        except (ProfileConfigError, ValueError) as error:
            status["value"] = display_escape_text(str(error))
            event.app.invalidate()
            return
        event.app.exit(result=selected)

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def render_footer() -> FormattedText:
        if status["value"]:
            return FormattedText([("class:error", status["value"])])
        return FormattedText(
            [("", " Edit directly · Ctrl-U clear · Enter create · Esc cancel")]
        )

    name_frame = name_field.frame
    root = HSplit(
        [
            Window(
                FormattedTextControl(
                    FormattedText([("class:study-name-label", " STUDY NAME")])
                ),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            name_frame,
            Window(
                FormattedTextControl(render_footer),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
        ],
        height=Dimension.exact(5),
    )
    app: Application[str | None] = Application(
        layout=Layout(root, focused_element=name_input),
        key_bindings=bindings,
        # Keep the normal terminal transcript visible; only these five rows
        # participate in prompt-toolkit rendering.
        full_screen=False,
        mouse_support=False,
        style=STUDY_NAME_STYLE,
        input=app_input,
        output=app_output,
    )
    return app.run()
