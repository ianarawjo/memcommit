"""Models for a shared writable multiline terminal input."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.widgets import Frame, TextArea


@dataclass(frozen=True)
class FramedMultilineInput:
    """A bordered writable input region with an independently named buffer."""

    frame: Frame
    text_area: TextArea

    @property
    def container(self) -> Frame:
        """Return the presentation container used in a layout."""

        return self.frame
