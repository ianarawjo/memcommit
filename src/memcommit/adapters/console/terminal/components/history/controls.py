"""Reusable History Items/Viewer controls, independent of operation approval."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence

from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceMoveResult,
)
from memcommit.adapters.console.terminal.components.frame import (
    bind_focused_frame_style,
)
from memcommit.adapters.console.terminal.components.history.model import (
    HistoryDetailRenderer,
    HistoryDetailView,
    HistoryPickerItem,
)
from memcommit.adapters.console.terminal.components.history.rendering import (
    VISIBLE_ROWS,
    detail_unit_position,
    render_history_detail,
    render_history_entry_fragments,
    visible_history_bounds,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    ScrollAnchor,
    build_scrollable_formatted_text_pane,
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.text_layout import (
    live_window_content_width,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
)


def validate_history_screen(
    context_name: str, *, title: str | None, require_tty: bool
) -> None:
    """Validate shared screen identity and terminal availability at entry."""

    if not isinstance(context_name, str) or not context_name:
        raise ValueError("History selection requires a Context name.")
    if title is not None and (not isinstance(title, str) or not title or "\n" in title):
        raise ValueError("History picker title must be non-empty text.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive history selection requires a terminal. "
            "Pass a checkpoint UID explicitly or use plain log output."
        )


class HistoryControls:
    """Own reading state and expose two composable keyboard surfaces.

    Checked identity and item activation are supplied by the composing screen:
    browsing a row must not implicitly change an operation's staged target.
    """

    def __init__(
        self,
        entries: Sequence[HistoryPickerItem],
        *,
        initial_details_open: bool | None = None,
        detail_renderer: HistoryDetailRenderer | None = None,
        empty_message: str | None = None,
        empty_detail: str | None = None,
        navigation: SessionWorkbenchNavigation | None = None,
        initial_uid: str | None = None,
        checked_uid: Callable[[], str | None] | None = None,
    ) -> None:
        self.options = tuple(entries)
        if not self.options and not empty_message:
            raise ValueError("No history entries are available to select.")
        for entry in self.options:
            if not isinstance(entry, HistoryPickerItem) or any(
                not isinstance(value, str)
                for value in (
                    entry.uid,
                    entry.timestamp,
                    entry.command,
                    entry.description,
                    entry.detail,
                )
            ):
                raise ValueError("History selection received an invalid entry.")
        if len({entry.uid for entry in self.options}) != len(self.options):
            raise ValueError("History selection received duplicate entry UIDs.")
        if detail_renderer is not None and not callable(detail_renderer):
            raise ValueError("History detail renderer must be callable.")
        if initial_details_open is not None and not isinstance(
            initial_details_open, bool
        ):
            raise ValueError("History initial detail state must be boolean.")
        if empty_detail is not None and (
            not isinstance(empty_detail, str) or not empty_detail
        ):
            raise ValueError("History empty detail must be non-empty text.")

        self.navigation = navigation or SessionWorkbenchNavigation(pane="items")
        self.navigation.focus("items")
        self.navigation.move_row(len(self.options), 0)
        if initial_uid is not None:
            self.preview_uid(initial_uid)
        self.navigation.preview_selected_row()
        self.details_open = (
            True if initial_details_open is None else initial_details_open
        )
        self.detail_renderer = detail_renderer or render_history_detail
        self.empty_message = empty_message
        self.empty_detail = empty_detail
        self.checked_uid = checked_uid or (lambda: None)
        self.detail_view: HistoryDetailView | None = None

        self.list_control = FormattedTextControl(
            text=self.render_entries,
            focusable=True,
            show_cursor=False,
        )
        self.options_window = Window(
            self.list_control,
            height=Dimension(
                min=1,
                preferred=min(len(self.options), VISIBLE_ROWS),
                max=VISIBLE_ROWS,
                weight=3,
            ),
            wrap_lines=False,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        self.detail_pane = build_scrollable_formatted_text_pane(
            "VIEWER",
            self.render_detail(),
            height=Dimension(min=6, preferred=14, weight=7),
        )
        self.items_frame = Frame(self.options_window, title="ITEMS")
        for control, frame in (
            (self.detail_pane.text_area, self.detail_pane.frame),
            (self.list_control, self.items_frame),
        ):
            bind_focused_frame_style(
                frame,
                is_focused=lambda control=control: get_app().layout.has_focus(control),
            )

    @property
    def frames(self) -> tuple[Frame, Frame]:
        return self.detail_pane.frame, self.items_frame

    @property
    def current_item(self) -> HistoryPickerItem | None:
        return self.options[self.navigation.row_index] if self.options else None

    @property
    def position(self) -> str:
        return (
            f"{self.navigation.row_index + 1}/{len(self.options)}"
            if self.options
            else "0/0"
        )

    def preview_uid(self, uid: str) -> None:
        row = next(
            (i for i, entry in enumerate(self.options) if entry.uid == uid), None
        )
        if row is None:
            raise ValueError("History preview must belong to the visible history.")
        self.navigation.move_row(len(self.options), row - self.navigation.row_index)
        self.navigation.preview_selected_row()

    def render_entries(self) -> StyleAndTextTuples:
        if not self.options:
            return [
                (
                    "class:report-neutral",
                    f"  {display_escape_text(self.empty_message or '')}",
                )
            ]
        start, end = visible_history_bounds(
            self.navigation.row_index, len(self.options)
        )
        visible = self.options[start:end]
        width = live_window_content_width(self.options_window, fallback_reserved=3)
        checked = self.checked_uid()
        fragments: StyleAndTextTuples = []
        for index in range(start, end):
            entry = self.options[index]
            selected = index == self.navigation.row_index
            if selected:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.extend(
                render_history_entry_fragments(
                    entry,
                    entries=visible,
                    selected=selected,
                    checked=entry.uid == checked,
                    available_width=width,
                )
            )
            if index < end - 1:
                fragments.append(("", "\n"))
        return fragments

    def render_detail(self) -> str | StyleAndTextTuples:
        if not self.options:
            rendered = self.empty_detail or " No history item is available."
        elif not self.details_open:
            rendered = " Select an item and press Enter to open its detail."
        else:
            rendered = self.detail_renderer(
                self.options[self.navigation.viewer_row_index]
            )
        self.detail_view = rendered if isinstance(rendered, HistoryDetailView) else None
        return rendered.content if isinstance(rendered, HistoryDetailView) else rendered

    def sync_detail(self, *, anchor: ScrollAnchor) -> None:
        self.detail_pane.set_formatted_text(self.render_detail(), anchor=anchor)

    def viewer_footer(self) -> str | None:
        if not get_app().layout.has_focus(self.detail_pane.text_area):
            return None
        view = self.detail_view
        progress = None
        if view is not None and view.unit_start_lines:
            row = self.detail_pane.text_area.buffer.document.cursor_position_row
            position = detail_unit_position(view.unit_start_lines, row)
            progress = f"{view.unit_label} {position}/{len(view.unit_start_lines)}"
        return (
            " FOCUS VIEWER"
            + (f" · {progress}" if progress is not None else "")
            + " · ↑/↓ scroll  Enter/Esc/Backspace items  "
            f"Tab switch  q close  ·  {self.position}"
        )

    def _move_items(self, _event, delta: int) -> SurfaceMoveResult:
        if not self.options:
            return "BOUNDARY"
        before = self.navigation.row_index
        self.navigation.move_and_preview_row(len(self.options), delta)
        if self.navigation.row_index == before:
            return "BOUNDARY"
        self.sync_detail(anchor="start")
        return "MOVED"

    def _move_viewer(self, event, delta: int) -> SurfaceMoveResult:
        return (
            "MOVED" if move_wrapped_read_cursor(event, direction=delta) else "BOUNDARY"
        )

    def _enter_viewer(self, delta: int) -> None:
        self.detail_pane.text_area.buffer.cursor_position = (
            0 if delta > 0 else len(self.detail_pane.text_area.text)
        )

    def _return_to_items(self, event) -> SurfaceActionResult:
        self.navigation.focus("items")
        event.app.layout.focus(self.list_control)
        return "HANDLED"

    def open_detail(self, event) -> SurfaceActionResult:
        if not self.options:
            return "HANDLED"
        self.details_open = True
        self.sync_detail(anchor="start")
        self.navigation.open_selected()
        event.app.layout.focus(self.detail_pane.text_area)
        return "ENTER_CHILD"

    def surfaces(
        self,
        *,
        back_items: Callable[..., SurfaceActionResult],
        activate_items: Callable[..., SurfaceActionResult] | None = None,
    ) -> tuple[FocusSurface, FocusSurface]:
        return (
            FocusSurface(
                "viewer",
                self.detail_pane.text_area,
                move_vertical=self._move_viewer,
                activate=self._return_to_items,
                back=self._return_to_items,
                on_focus=lambda: self.navigation.focus("viewer"),
                on_vertical_enter=self._enter_viewer,
            ),
            FocusSurface(
                "items",
                self.list_control,
                move_vertical=self._move_items,
                activate=activate_items or self.open_detail,
                back=back_items,
                on_focus=lambda: self.navigation.focus("items"),
            ),
        )

    def bind_viewer_keys(self, bindings: KeyBindings) -> None:
        viewer_focused = has_focus(self.detail_pane.text_area)

        @bindings.add("pageup", filter=viewer_focused, eager=True)
        def page_up(event) -> None:
            scroll_wrapped_page(event, direction=-1)

        @bindings.add("pagedown", filter=viewer_focused, eager=True)
        def page_down(event) -> None:
            scroll_wrapped_page(event, direction=1)

        @bindings.add("home", filter=viewer_focused, eager=True)
        def home(event) -> None:
            self.detail_pane.text_area.buffer.cursor_position = 0
            self.detail_pane.text_area.window.vertical_scroll = 0
            self.detail_pane.text_area.window.vertical_scroll_2 = 0
            event.app.invalidate()

        @bindings.add("end", filter=viewer_focused, eager=True)
        def end(event) -> None:
            self.detail_pane.text_area.buffer.cursor_position = len(
                self.detail_pane.text_area.text
            )
            event.app.invalidate()
