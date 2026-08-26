"""Construction and trusted updates for read-only pane components."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.layout import (
    AnyDimension,
    ConditionalContainer,
    Float,
    FloatContainer,
    FormattedTextControl,
    Window,
)
from prompt_toolkit.layout.containers import AnyContainer
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.interfaces.tui.components.scrollable_pane.model import (
    ScrollAnchor,
    ScrollableFormattedTextPane,
    ScrollableTextPane,
)
from memcommit.interfaces.tui.components.scrollable_pane.scrollbar import (
    WrappedScrollbarMargin,
)
from memcommit.interfaces.tui.core.buffers import next_buffer_name


class _MutableFormattedTextLexer(Lexer):
    """Keep trusted semantic styles aligned with a read-only text buffer."""

    def __init__(self) -> None:
        self._lines: tuple[StyleAndTextTuples, ...] = ([],)
        self._generation = 0

    def replace(self, value: str | StyleAndTextTuples) -> str:
        fragments = [
            (style, safe_terminal_text(text))
            for style, text, *_ in to_formatted_text(value)
        ]
        self._lines = tuple(
            [(style, text) for style, text, *_ in line if text]
            for line in split_lines(fragments)
        ) or ([],)
        self._generation += 1
        return "\n".join("".join(text for _style, text in line) for line in self._lines)

    def lex_document(self, document: Document):
        lines = self._lines

        def get_line(line_number: int) -> StyleAndTextTuples:
            if 0 <= line_number < len(lines):
                return list(lines[line_number])
            if 0 <= line_number < len(document.lines):
                return [("", document.lines[line_number])]
            return []

        return get_line

    def invalidation_hash(self):
        return self._generation


def equal_pane_height(
    *,
    minimum: int = 4,
    preferred: int | None = None,
    maximum: int | None = None,
    weight: int = 1,
) -> Dimension:
    """Return a height for sibling panes that should share available space."""

    return Dimension(min=minimum, preferred=preferred, max=maximum, weight=weight)


def build_scrollable_text_pane(
    title: str,
    text: str = "",
    *,
    buffer_name: str | None = None,
    height: AnyDimension = None,
    wrap_lines: bool = True,
    focusable: bool = True,
    style: str = "",
    frame_style: str = "",
    notification: Callable[[], bool] | None = None,
    lexer: Lexer | None = None,
) -> ScrollableTextPane:
    """Build one independently scrollable, read-only framed component."""

    text_area = TextArea(
        text=safe_terminal_text(text),
        multiline=True,
        lexer=lexer,
        focusable=focusable,
        focus_on_click=focusable,
        wrap_lines=wrap_lines,
        read_only=True,
        scrollbar=True,
        style=style,
        name=buffer_name or next_buffer_name("pane"),
    )
    scrollbar_margin = WrappedScrollbarMargin(display_arrows=True)
    text_area.window.right_margins = [scrollbar_margin]
    frame = Frame(
        text_area,
        title=display_escape_text(title),
        style=frame_style,
        height=height if height is not None else equal_pane_height(),
    )
    presentation_container: AnyContainer | None = None
    if notification is not None:
        badge = ConditionalContainer(
            Window(
                FormattedTextControl([("class:memcommit.notification", "●")]),
                width=Dimension.exact(1),
                height=Dimension.exact(1),
                dont_extend_width=True,
                dont_extend_height=True,
            ),
            filter=Condition(notification),
        )
        presentation_container = FloatContainer(
            content=frame,
            floats=[Float(content=badge, top=0, right=2, width=1, height=1)],
        )
    return ScrollableTextPane(
        frame=frame,
        text_area=text_area,
        scrollbar_margin=scrollbar_margin,
        presentation_container=presentation_container,
    )


def build_scrollable_formatted_text_pane(
    title: str,
    value: str | StyleAndTextTuples = "",
    *,
    buffer_name: str | None = None,
    height: AnyDimension = None,
    wrap_lines: bool = True,
    focusable: bool = True,
    style: str = "",
    frame_style: str = "",
) -> ScrollableFormattedTextPane:
    """Build a styled report pane on the common cursor-backed viewport."""

    lexer = _MutableFormattedTextLexer()
    plain_text = lexer.replace(value)
    pane = build_scrollable_text_pane(
        title,
        plain_text,
        buffer_name=buffer_name,
        height=height,
        wrap_lines=wrap_lines,
        focusable=focusable,
        style=style,
        frame_style=frame_style,
        lexer=lexer,
    )
    return ScrollableFormattedTextPane(pane=pane, lexer=lexer)


def set_scrollable_pane_text(
    pane: ScrollableTextPane,
    text: str,
    *,
    anchor: ScrollAnchor = "preserve",
) -> None:
    """Replace pane text without accidentally resetting its reading position."""

    if anchor not in {"preserve", "start", "end"}:
        raise ValueError("anchor must be 'preserve', 'start', or 'end'")

    safe_text = safe_terminal_text(text)
    buffer = pane.text_area.buffer
    window = pane.text_area.window
    old_cursor = buffer.cursor_position
    old_vertical_scroll = window.vertical_scroll
    old_vertical_scroll_2 = window.vertical_scroll_2
    old_horizontal_scroll = window.horizontal_scroll
    cursor_position = (
        0
        if anchor == "start"
        else len(safe_text)
        if anchor == "end"
        else min(old_cursor, len(safe_text))
    )
    buffer.set_document(
        Document(safe_text, cursor_position=cursor_position),
        bypass_readonly=True,
    )
    if pane.scrollbar_margin is not None:
        pane.scrollbar_margin.invalidate()

    if anchor == "start":
        window.vertical_scroll = 0
        window.vertical_scroll_2 = 0
        window.horizontal_scroll = 0
    elif anchor == "end":
        window.vertical_scroll = safe_text.count("\n")
        window.vertical_scroll_2 = 0
        window.horizontal_scroll = 0
    else:
        window.vertical_scroll = old_vertical_scroll
        window.vertical_scroll_2 = old_vertical_scroll_2
        window.horizontal_scroll = old_horizontal_scroll
