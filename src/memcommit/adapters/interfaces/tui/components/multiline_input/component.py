"""Construction of the shared writable multiline terminal input."""

from __future__ import annotations

from itertools import count

from prompt_toolkit.layout import AnyDimension
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.adapters.interfaces.tui.components.multiline_input.model import (
    FramedMultilineInput,
)


_BUFFER_SERIAL = count(1)


def _next_buffer_name() -> str:
    return f"memcommit-multiline-{next(_BUFFER_SERIAL)}"


def build_framed_multiline_input(
    title: str,
    *,
    text: str = "",
    prompt: str = "> ",
    buffer_name: str | None = None,
    height: AnyDimension = None,
    scrollbar: bool = True,
    style: str = "",
    frame_style: str = "",
) -> FramedMultilineInput:
    """Build a writable, wrapping input with component-owned scrolling."""

    text_area = TextArea(
        text=text,
        multiline=True,
        focusable=True,
        focus_on_click=True,
        wrap_lines=True,
        read_only=False,
        scrollbar=scrollbar,
        prompt=prompt,
        style=style,
        name=buffer_name or _next_buffer_name(),
    )
    frame = Frame(
        text_area,
        title=display_escape_text(title),
        style=frame_style,
        height=(height if height is not None else Dimension(min=5, preferred=6, max=9)),
    )
    return FramedMultilineInput(frame=frame, text_area=text_area)
