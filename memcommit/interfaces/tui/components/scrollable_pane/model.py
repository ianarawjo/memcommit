"""Values exposed by the shared read-only pane components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.layout.containers import AnyContainer
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.interfaces.tui.components.scrollable_pane.scrollbar import (
    WrappedScrollbarMargin,
)


ScrollAnchor = Literal["preserve", "start", "end"]


@dataclass(frozen=True)
class ScrollableTextPane:
    """A framed, focusable, read-only text viewport with its own buffer."""

    frame: Frame
    text_area: TextArea
    scrollbar_margin: WrappedScrollbarMargin | None = None
    presentation_container: AnyContainer | None = None

    @property
    def container(self) -> AnyContainer:
        return self.presentation_container or self.frame

    def set_text(self, text: str, *, anchor: ScrollAnchor = "preserve") -> None:
        from memcommit.interfaces.tui.components.scrollable_pane.component import (
            set_scrollable_pane_text,
        )

        set_scrollable_pane_text(self, text, anchor=anchor)


@dataclass(frozen=True)
class ScrollableFormattedTextPane:
    """The common read-only pane with dynamic formatted-text presentation."""

    pane: ScrollableTextPane
    lexer: Lexer

    @property
    def frame(self) -> Frame:
        return self.pane.frame

    @property
    def text_area(self) -> TextArea:
        return self.pane.text_area

    @property
    def container(self) -> AnyContainer:
        return self.pane.container

    def set_formatted_text(
        self,
        value: str | StyleAndTextTuples,
        *,
        anchor: ScrollAnchor = "preserve",
    ) -> None:
        replace = getattr(self.lexer, "replace")
        self.pane.set_text(replace(value), anchor=anchor)
