"""Operation-neutral controls for one exact writable name."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from typing import Callable

from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import Completer
from prompt_toolkit.layout import AnyDimension
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.adapters.console.text import safe_terminal_text
from memcommit.adapters.console.tui.components.frame import build_focused_frame


_BUFFER_SERIAL = count(1)


def _next_buffer_name(kind: str) -> str:
    """Return an app-safe buffer name when a caller does not supply one."""
    return f"memcommit-{kind}-{next(_BUFFER_SERIAL)}"


@dataclass(frozen=True)
class ExactNameFieldView:
    """Operation-neutral contract for one exact, single-line name."""

    value: str
    label: str = "NAME"
    state: str = ""
    detail: str = "Enter to continue with this exact name."
    validate: Callable[[str], object] | None = None
    value_label: str = "Name"
    strip_candidate: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError(f"{self.value_label} must be text.")
        for value, label in (
            (self.label, "Name-field label"),
            (self.detail, "Name-field detail"),
            (self.value_label, "Name-field value label"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty text.")
        if any(character in self.value for character in "\r\n"):
            raise ValueError(f"{self.value_label} must stay on one line.")
        if any(character in self.label for character in "\r\n"):
            raise ValueError("Name-field label must stay on one line.")
        if not isinstance(self.state, str) or any(
            character in self.state for character in "\r\n"
        ):
            raise ValueError("Name-field state must be one-line text.")
        if self.validate is not None and not callable(self.validate):
            raise TypeError("Name-field validation must be callable.")
        if not isinstance(self.strip_candidate, bool):
            raise TypeError("Name-field strip policy must be boolean.")

    def validate_value(self, value: str) -> str:
        """Validate one candidate without deciding how it is persisted."""
        if not isinstance(value, str):
            raise ValueError(f"{self.value_label} must be nonempty text.")
        candidate = value.strip() if self.strip_candidate else value
        if not candidate.strip():
            raise ValueError(f"{self.value_label} must be nonempty text.")
        if any(character in candidate for character in "\r\n"):
            raise ValueError(f"{self.value_label} must stay on one line.")
        if self.validate is not None:
            self.validate(candidate)
        return candidate


@dataclass
class ExactNameInputControl:
    """Embeddable exact-name input without a surrounding layout frame."""

    view: ExactNameFieldView
    input: TextArea

    @classmethod
    def create(
        cls,
        view: ExactNameFieldView,
        *,
        input_name: str | None = None,
        prompt: str = "› ",
        input_style: str = "",
        completer: Completer | None = None,
        complete_while_typing: bool = True,
        width: AnyDimension = None,
        dont_extend_width: bool = False,
    ) -> "ExactNameInputControl":
        """Build the writable field without imposing box or host semantics."""
        input_area = TextArea(
            text=view.value,
            multiline=False,
            completer=completer,
            complete_while_typing=complete_while_typing,
            prompt=prompt,
            focusable=True,
            focus_on_click=True,
            wrap_lines=False,
            width=width,
            height=Dimension.exact(1),
            dont_extend_width=dont_extend_width,
            style=input_style,
            name=input_name or _next_buffer_name("exact-name"),
        )
        input_area.buffer.cursor_position = len(view.value)
        return cls(view=view, input=input_area)

    @property
    def text(self) -> str:
        return self.input.text

    def set_text(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("Exact name field text must be text.")
        self.input.text = value
        self.input.buffer.cursor_position = len(value)

    def validate_candidate(self) -> str:
        return self.view.validate_value(self.input.text)


@dataclass
class ExactNameFieldControl:
    """Exact-name input composed with common focused-frame chrome."""

    input_control: ExactNameInputControl
    frame: Frame

    @classmethod
    def create(
        cls,
        view: ExactNameFieldView,
        *,
        input_name: str | None = None,
        prompt: str = "› ",
        height: AnyDimension = None,
        input_style: str = "",
        frame_style: str = "",
        frame_title: str | None = None,
    ) -> "ExactNameFieldControl":
        """Compose the standalone input with one reusable focused frame."""
        input_control = ExactNameInputControl.create(
            view,
            input_name=input_name,
            prompt=prompt,
            input_style=input_style,
        )
        title = (
            view.label + (f" · {view.state}" if view.state else "")
            if frame_title is None
            else frame_title
        )
        frame = build_focused_frame(
            input_control.input,
            title=safe_terminal_text(title),
            is_focused=lambda: get_app().layout.has_focus(input_control.input),
            style=frame_style,
            height=height if height is not None else Dimension.exact(3),
        )
        return cls(input_control=input_control, frame=frame)

    @property
    def view(self) -> ExactNameFieldView:
        return self.input_control.view

    @property
    def input(self) -> TextArea:
        return self.input_control.input

    @property
    def text(self) -> str:
        return self.input_control.text

    def set_text(self, value: str) -> None:
        self.input_control.set_text(value)

    def validate_candidate(self) -> str:
        return self.input_control.validate_candidate()
