"""Editable Help command handoff without parent-shell integration."""

from __future__ import annotations

import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application
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
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.components.exact_command_review import (
    EditableExactCommandControl,
    ExactCommandDraft,
    ExactCommandForm,
    ExactCommandFormField,
    CommandReview,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)


CommandRunner = Callable[..., subprocess.CompletedProcess[object]]


def _parse_selected_line(command_name: str, command_line: str) -> tuple[str, ...]:
    if not isinstance(command_name, str) or not command_name:
        raise ValueError("Help command handoff requires an operation name.")
    if not isinstance(command_line, str) or not command_line.strip():
        raise ValueError("Help command handoff requires a command line.")
    try:
        argv = tuple(shlex.split(command_line))
    except ValueError as error:
        raise ValueError(
            f"Selected Help command has invalid quoting: {error}"
        ) from error
    prefix = ("mem", command_name)
    if argv[:2] != prefix:
        raise ValueError(
            "Selected Help command must retain its exact operation prefix "
            f"'{shlex.join(prefix)}'."
        )
    return argv


def edit_help_command(
    command_name: str,
    command_line: str,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> tuple[str, ...] | None:
    """Edit one selected Help form and return an exact argv on Enter."""

    initial = _parse_selected_line(command_name, command_line)
    prefix = initial[:2]
    current: dict[str, tuple[str, ...]] = {"argv": initial}
    form = ExactCommandForm(
        command=prefix,
        usage=command_line,
        fields=(
            ExactCommandFormField(
                "ARGUMENTS",
                "edit the selected command's operands and options before running it",
            ),
        ),
    )

    def review() -> CommandReview:
        return CommandReview(
            argv=current["argv"],
            effects=("Help closes before this exact command runs in a child process.",),
        )

    def apply_argv(argv: tuple[str, ...]) -> None:
        if argv[:2] != prefix:
            raise ValueError(
                f"Help edits only the selected '{shlex.join(prefix)}' operation."
            )
        current["argv"] = argv

    command = EditableExactCommandControl.create(
        ExactCommandDraft(
            review=review,
            apply_argv=apply_argv,
            form=form,
        ),
        action_label="PRESS ENTER TO RUN THE EDITED COMMAND",
        incomplete_action="FIX THE RED COMMAND BEFORE RUNNING",
        input_name="help-command-handoff",
    )
    bindings = KeyBindings()
    status = {"value": ""}

    @bindings.add("enter")
    def _run(event) -> None:
        if not command.validate_current(event.app):
            status["value"] = "INVALID COMMAND · FIX THE RED EDITABLE FIELD"
            event.app.invalidate()
            return
        event.app.exit(result=current["argv"])

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def footer_text() -> str:
        if status["value"]:
            return " " + display_escape_text(status["value"])
        if command.valid:
            return " Edit arguments · Enter run · Esc cancel"
        return " Fix the red command · Enter recheck · Esc cancel"

    header = Window(
        FormattedTextControl(
            " MEM HELP · EDIT SELECTED COMMAND\n"
            " THE OPERATION IS FIXED; REVIEW ITS ARGUMENTS BEFORE RUNNING"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    body = HSplit(
        [
            header,
            Window(height=Dimension.exact(1), char="─"),
            command.body,
            Window(height=Dimension.exact(1), char="─"),
            Window(
                FormattedTextControl(footer_text),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
        ]
    )
    application: Application[tuple[str, ...] | None] = Application(
        layout=Layout(body, focused_element=command.input),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Help command editing requires an interactive terminal.")
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return None


def run_help_command(
    argv: Sequence[str],
    *,
    runner: CommandRunner = subprocess.run,
) -> int:
    """Run one edited Mem command without interpreting shell syntax."""

    values = tuple(argv)
    if len(values) < 2 or values[0] != "mem":
        raise ValueError("Help command handoff requires an exact Mem argv.")
    try:
        result = runner(values, check=False)
    except KeyboardInterrupt:
        return 130
    except OSError as error:
        raise RuntimeError(f"Could not run the selected command: {error}") from error
    return int(result.returncode)


__all__ = ["edit_help_command", "run_help_command"]
