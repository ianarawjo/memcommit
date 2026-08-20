"""Common prompt-toolkit surface for editing one proposed command."""

from __future__ import annotations

from dataclasses import dataclass, field

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer, Dimension, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea

from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.components.exact_command_review.form import (
    ExactCommandDraft,
)


@dataclass
class EditableExactCommandControl:
    """Always-visible one-line editor synchronized with an operation form."""

    draft: ExactCommandDraft
    action_label: str
    incomplete_action: str
    review_control: FormattedTextControl
    input: TextArea
    body: HSplit
    _changing_buffer: bool = field(default=False, init=False)

    @classmethod
    def create(
        cls,
        draft: ExactCommandDraft,
        *,
        action_label: str,
        incomplete_action: str,
        input_name: str,
    ) -> "EditableExactCommandControl":
        for value, label in (
            (action_label, "Proposed-command action"),
            (incomplete_action, "Proposed-command incomplete action"),
            (input_name, "Proposed-command input name"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty text.")

        holder: dict[str, EditableExactCommandControl] = {}
        review_control = FormattedTextControl(
            lambda: holder["value"]._render_error(),
            focusable=False,
            show_cursor=False,
        )
        input_area = TextArea(
            multiline=False,
            prompt="› ",
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
        self.draft.synchronize(self.input.text)
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

    def sync_from_review(self, app=None) -> bool:
        """Project a changed upper form into the editable command field."""

        try:
            line = self.draft.accept_review()
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            line = self.draft.reject_review(error)
        self._replace_text(line)
        if app is not None:
            app.invalidate()
        return self.draft.valid

    def validate_current(self, app=None) -> bool:
        """Revalidate the visible line before the operation-owned approval."""

        valid = self.draft.synchronize(self.input.text)
        if app is not None:
            app.invalidate()
        return valid


__all__ = ["EditableExactCommandControl"]
