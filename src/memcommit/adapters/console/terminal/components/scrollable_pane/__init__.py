"""Reusable framed, wrapped, read-only terminal panes."""

from memcommit.adapters.console.terminal.components.scrollable_pane.component import (
    build_scrollable_formatted_text_pane,
    build_scrollable_text_pane,
    equal_pane_height,
    set_scrollable_pane_text,
)
from memcommit.adapters.console.terminal.components.scrollable_pane.model import (
    ScrollAnchor,
    ScrollableFormattedTextPane,
    ScrollableTextPane,
)
from memcommit.adapters.console.terminal.components.scrollable_pane.navigation import (
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.components.scrollable_pane.scrollbar import (
    WrappedScrollbarMargin,
)

__all__ = [
    "ScrollAnchor",
    "ScrollableFormattedTextPane",
    "ScrollableTextPane",
    "WrappedScrollbarMargin",
    "build_scrollable_formatted_text_pane",
    "build_scrollable_text_pane",
    "equal_pane_height",
    "move_wrapped_read_cursor",
    "scroll_wrapped_page",
    "set_scrollable_pane_text",
]
