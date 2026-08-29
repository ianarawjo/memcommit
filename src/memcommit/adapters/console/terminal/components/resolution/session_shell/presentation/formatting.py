"""Shared pure text formatting for Resolution Session presentations."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
)
from memcommit.application.capabilities.resolution.workbench import ResolutionItem


# Report chrome and explanatory prose stay neutral white. Lavender identifies
# an actual Memory object only; using it for whole cards blurs data and report
# structure into the same visual class.
RESOLUTION_WORKBENCH_STYLE = SEMANTIC_VIEWER_STYLE


def _line(value: str, limit: int = 100) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def _item_kind_label(item: ResolutionItem) -> str:
    """Render the operation-owned label without leaking its storage token."""

    return safe_terminal_text(item.display_kind)


def _indented(value: str, indent: str = "       ") -> str:
    return "\n".join(indent + line for line in value.splitlines())


def _visual_width(value: str) -> int:
    return terminal_cell_width(value)


def _visual_pad(value: str, width: int) -> str:
    return value + (" " * max(0, width - _visual_width(value)))


def _visual_wrap(value: str, width: int) -> list[str]:
    """Wrap terminal text by display cells while retaining paragraph breaks."""
    return wrap_terminal_text(safe_terminal_text(value), width)


def _source_memory_lines(content: str, content_width: int) -> tuple[str, ...]:
    """Wrap one Memory for its nested reading viewport, not outer focus."""

    # Reserve the first-row short UID and continuation indentation. These rows
    # are presentation-only offsets inside one stable SOURCE_MEMORY section.
    return tuple(_visual_wrap(content, max(1, content_width - 16)))
