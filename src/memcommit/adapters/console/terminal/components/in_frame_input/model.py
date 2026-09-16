"""Models for attaching writable fields below a read pane."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.layout import AnyDimension
from prompt_toolkit.widgets import TextArea


@dataclass(frozen=True)
class InFrameInputSection:
    """One labeled field embedded below a pane's read surface.

    ``allow_read_only`` is reserved for visibly locked direct-edit fields; a
    normal conversational composer must remain writable.
    """

    title: str
    text_area: TextArea
    height: AnyDimension = None
    allow_read_only: bool = False
