"""Layout manager for pane-local writable input sections."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.layout import AnyDimension, FormattedTextControl, HSplit, Window
from prompt_toolkit.layout.containers import AnyContainer

from memcommit.adapters.console.text import display_escape_text
from memcommit.adapters.interfaces.tui.components.in_frame_input.model import (
    InFrameInputSection,
)
from memcommit.adapters.interfaces.tui.components.scrollable_pane import ScrollableTextPane


@dataclass(frozen=True)
class _PaneBaseLayout:
    body: AnyContainer
    height: AnyDimension


class InFrameInputManager:
    """Move writable fields among read panes without nesting another Frame.

    One manager owns one set of live pane containers. Attaching a field first
    restores the previous host, because prompt-toolkit must not see the same
    writable ``TextArea`` through two live layout branches at once.
    """

    def __init__(self, *panes: ScrollableTextPane) -> None:
        if not panes:
            raise ValueError("at least one pane is required")
        if len({id(pane) for pane in panes}) != len(panes):
            raise ValueError("panes must be distinct")
        self._panes = {id(pane): pane for pane in panes}
        self._base = {
            id(pane): _PaneBaseLayout(
                body=pane.frame.body,
                height=pane.frame.container.height,
            )
            for pane in panes
        }
        self._active_pane: ScrollableTextPane | None = None
        self._active_sections: tuple[InFrameInputSection, ...] = ()

    @property
    def active_pane(self) -> ScrollableTextPane | None:
        """Return the pane currently hosting writable fields, if any."""

        return self._active_pane

    @property
    def active_sections(self) -> tuple[InFrameInputSection, ...]:
        """Return the currently embedded fields in display order."""

        return self._active_sections

    def show(
        self,
        pane: ScrollableTextPane,
        *sections: InFrameInputSection,
        height: AnyDimension = None,
    ) -> None:
        """Show labeled inputs inside ``pane`` and retain its scroll surface."""

        if id(pane) not in self._panes:
            raise ValueError("pane is not registered with this manager")
        if not sections:
            self.clear()
            return

        text_areas = [section.text_area for section in sections]
        if len({id(text_area) for text_area in text_areas}) != len(text_areas):
            raise ValueError("input TextAreas must be distinct")
        if any(
            section.text_area.buffer.read_only() and not section.allow_read_only
            for section in sections
        ):
            raise ValueError("embedded input TextAreas must be writable")
        if pane.text_area in text_areas:
            raise ValueError("a pane's read TextArea cannot be its input")

        self.clear()
        children: list[AnyContainer] = [pane.text_area]
        for section in sections:
            children.extend(
                [
                    Window(
                        FormattedTextControl(display_escape_text(section.title)),
                        height=1,
                        char="─",
                        style="class:embedded-input.separator",
                    ),
                    HSplit([section.text_area], height=section.height),
                ]
            )
        pane.frame.body = HSplit(children)
        if height is not None:
            pane.frame.container.height = height
        self._active_pane = pane
        self._active_sections = tuple(sections)

    def clear(self) -> None:
        """Detach all inputs and restore the active pane's original layout."""

        pane = self._active_pane
        if pane is None:
            return
        base = self._base[id(pane)]
        pane.frame.body = base.body
        pane.frame.container.height = base.height
        self._active_pane = None
        self._active_sections = ()
