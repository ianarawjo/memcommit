"""Common prompt-toolkit surface for editing one proposed command."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer, Dimension, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.components.command_editor.form import (
    CommandDraft,
)


@dataclass
class CommandEditorControl:
    """Always-visible one-line editor synchronized with an operation form."""

    draft: CommandDraft
    action_label: str
    incomplete_action: str
    command_prefix: str
    review_control: FormattedTextControl
    input: TextArea
    body: HSplit
    _changing_buffer: bool = field(default=False, init=False)
    _last_review_signature: tuple[str, str] | None = field(default=None, init=False)

    @classmethod
    def create(
        cls,
        draft: CommandDraft,
        *,
        action_label: str,
        incomplete_action: str,
        input_name: str,
    ) -> "CommandEditorControl":
        for value, label in (
            (action_label, "Proposed-command action"),
            (incomplete_action, "Proposed-command incomplete action"),
            (input_name, "Proposed-command input name"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty text.")

        holder: dict[str, CommandEditorControl] = {}
        command_prefix = shlex.join(draft.form.command)
        review_control = FormattedTextControl(
            lambda: holder["value"]._render_error(),
            focusable=False,
            show_cursor=False,
        )
        input_area = TextArea(
            multiline=False,
            # The operation is presentation, not buffer content: destructive
            # editing keys can revise arguments without changing what runs.
            prompt=f"› {command_prefix} ",
            focusable=True,
            focus_on_click=True,
            wrap_lines=False,
            height=Dimension.exact(1),
            name=input_name,
        )
        body = HSplit(
            [
                input_area,
                ConditionalContainer(
                    Window(
                        review_control,
                        height=Dimension.exact(1),
                        dont_extend_height=True,
                    ),
                    filter=Condition(lambda: not draft.valid),
                ),
            ]
        )
        control = cls(
            draft=draft,
            action_label=action_label,
            incomplete_action=incomplete_action,
            command_prefix=command_prefix,
            review_control=review_control,
            input=input_area,
            body=body,
        )
        holder["value"] = control
        input_area.window.style = control._input_style
        input_area.buffer.on_text_changed += control._on_text_changed
        control.sync_from_review()
        return control

    @property
    def active_control(self):
        return self.input

    @property
    def valid(self) -> bool:
        return self.draft.valid

    def is_focused(self) -> bool:
        return get_app().layout.has_focus(self.input)

    @property
    def frame_title(self) -> str:
        self.sync_if_review_changed()
        return "COMMAND · RUNNABLE" if self.draft.valid else "COMMAND · INVALID"

    def frame_style(self) -> str:
        return (
            "class:memcommit.focused"
            if self.draft.valid
            else "class:impact.remove"
        )

    def _input_style(self) -> str:
        return "class:report-neutral"

    def _on_text_changed(self, _buffer) -> None:
        if self._changing_buffer:
            return
        if self.draft.synchronize(self.command_line()):
            # A valid command has already moved the operation-owned state.
            # Remember its canonical projection without replacing the person's
            # still-focused spelling or argument order.
            try:
                self._last_review_signature = ("VALID", self.draft.command_line())
            except (KeyError, OSError, RuntimeError, TypeError, ValueError):
                self._last_review_signature = None
        try:
            get_app().invalidate()
        except RuntimeError:
            # Construction and pure component tests have no running app.
            pass

    def _render_error(self) -> list[tuple[str, str]]:
        return [
            (
                "class:impact.remove",
                " " + display_escape_text(self.draft.error),
            )
        ]

    def _replace_text(self, text: str) -> None:
        self._changing_buffer = True
        try:
            self.input.text = text
            self.input.buffer.cursor_position = len(text)
        finally:
            self._changing_buffer = False

    def command_line(self) -> str:
        """Return the fixed operation plus the currently editable arguments."""

        if not self.input.text:
            return self.command_prefix
        return f"{self.command_prefix} {self.input.text}"

    def _editable_arguments(self, line: str) -> str:
        if line == self.command_prefix:
            return ""
        marker = self.command_prefix + " "
        if not line.startswith(marker):
            raise RuntimeError(
                "Reviewed command does not match its fixed operation prefix."
            )
        return line[len(marker) :]

    def sync_from_review(self, app=None) -> bool:
        """Project a changed upper form into the editable command field."""

        try:
            line = self.draft.accept_review()
            signature = ("VALID", line)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            line = self.draft.reject_review(error)
            signature = ("INVALID", str(error))
        self._replace_text(self._editable_arguments(line))
        self._last_review_signature = signature
        if app is not None:
            app.invalidate()
        return self.draft.valid

    def sync_if_review_changed(self) -> bool:
        """Refresh after upper controls change without erasing invalid input.

        A valid command-buffer edit updates the operation state first and
        records the resulting canonical review signature.  A later render can
        therefore distinguish an upper-control change from the buffer edit
        that caused it.  Invalid command text leaves the signature untouched,
        so repainting never silently restores the last valid command.
        """

        try:
            line = self.draft.command_line()
            signature = ("VALID", line)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            signature = ("INVALID", str(error))
        if signature == self._last_review_signature:
            return self.draft.valid
        return self.sync_from_review()

    def validate_current(self, app=None) -> bool:
        """Revalidate the visible line before the operation-owned approval."""

        valid = self.draft.synchronize(self.command_line())
        if app is not None:
            app.invalidate()
        return valid


__all__ = ["CommandEditorControl"]
