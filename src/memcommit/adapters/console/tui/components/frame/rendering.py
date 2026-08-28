"""Shared frame chrome and top-to-bottom screen composition."""

from __future__ import annotations

from typing import Callable

from prompt_toolkit.layout import (
    AnyDimension,
    ConditionalContainer,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.containers import AnyContainer
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import Margin
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.tui.components.frame.model import TuiRegion


class _BlankMargin(Margin):
    """Reserve terminal columns without introducing visible separator chrome."""

    def __init__(self, width: int) -> None:
        self.width = width

    def get_width(self, get_ui_content) -> int:
        del get_ui_content
        return self.width

    def create_margin(self, window_render_info, width: int, height: int):
        del window_render_info
        fragments: list[tuple[str, str]] = []
        for row in range(height):
            fragments.append(("", " " * width))
            if row < height - 1:
                fragments.append(("", "\n"))
        return fragments


def horizontal_rule(*, right_gutter: int = 0) -> Window:
    """Return a shared fixed-height separator with an optional blank gutter."""

    if (
        not isinstance(right_gutter, int)
        or isinstance(right_gutter, bool)
        or right_gutter < 0
    ):
        raise ValueError("Horizontal-rule gutter must be a nonnegative integer.")

    return Window(
        height=Dimension.exact(1),
        char="─",
        dont_extend_height=True,
        right_margins=([_BlankMargin(right_gutter)] if right_gutter else None),
    )


def bind_focused_frame_style(
    frame: Frame,
    *,
    is_focused: Callable[[], bool],
) -> None:
    """Render focused chrome with light-blue styling and heavy box glyphs."""

    base_style = frame.container.style

    def focused_style() -> str:
        resolved = base_style() if callable(base_style) else base_style
        return f"{resolved} class:memcommit.focused" if is_focused() else resolved

    frame.container.style = focused_style
    heavy_border = {
        "┌": "┏",
        "─": "━",
        "┐": "┓",
        "│": "┃",
        "└": "┗",
        "┘": "┛",
        "|": "┃",
    }

    def bind_border_chars(container: AnyContainer) -> None:
        if isinstance(container, Window):
            normal = container.char
            if isinstance(normal, str) and normal in heavy_border:
                heavy = heavy_border[normal]
                container.char = lambda normal=normal, heavy=heavy: (
                    heavy if is_focused() else normal
                )
            return
        if isinstance(container, ConditionalContainer):
            bind_border_chars(container.content)
            return
        if isinstance(container, (HSplit, VSplit)):
            for child in container.children:
                bind_border_chars(child)

    bind_border_chars(frame.container)


def build_focused_frame(
    body: AnyContainer,
    *,
    title,
    is_focused: Callable[[], bool],
    height: AnyDimension = None,
    style: str = "",
) -> Frame:
    """Compose arbitrary content with the shared focused-frame presentation."""

    if not callable(is_focused):
        raise TypeError("Focused-frame state must be callable.")
    frame = Frame(body, title=title, height=height, style=style)
    bind_focused_frame_style(frame, is_focused=is_focused)
    return frame


def build_tui_frame(*regions: TuiRegion) -> HSplit:
    """Compose operation-owned regions into one full-screen vertical frame."""

    children: list[AnyContainer] = []
    for region in regions:
        if region.separator_before:
            children.append(Window(height=1, char="─"))
        children.append(region.container)
    return HSplit(children)
