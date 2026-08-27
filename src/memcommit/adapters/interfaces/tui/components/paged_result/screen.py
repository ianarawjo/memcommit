"""Shared compact pager shell for already-frozen result rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.interfaces.console.terminal import require_interactive_terminal
from memcommit.adapters.interfaces.tui.components.paged_result.model import PagedResultState
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)


@dataclass(frozen=True)
class PagedResultRenderer:
    """Supply operation meaning while the shared shell owns navigation."""

    item_count: int
    header: Callable[[PagedResultState], StyleAndTextTuples]
    row: Callable[[int], StyleAndTextTuples]
    header_height: int
    page_size: int = 10
    row_window_height: int | None = None
    footer: str = (
        "↑/↓ move · ←/→ or PgUp/PgDn page · Home/End boundary · Esc/q close"
    )

    def __post_init__(self) -> None:
        if not callable(self.header) or not callable(self.row):
            raise TypeError("Paged result renderers require header and row callbacks.")
        if self.header_height < 1:
            raise ValueError("Paged result headers require at least one line.")
        if self.row_window_height is not None and self.row_window_height < 1:
            raise ValueError("Paged result row window height must be positive.")


def run_paged_result(
    renderer: PagedResultRenderer,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> int:
    """Inspect a bounded result window and return the last focused item index."""

    if not isinstance(renderer, PagedResultRenderer):
        raise TypeError("Compact result paging requires a PagedResultRenderer.")
    if require_tty:
        require_interactive_terminal("Compact result pager")
    state = PagedResultState(
        renderer.item_count,
        page_size=renderer.page_size,
    )
    bindings = KeyBindings()

    def move(event, delta: int) -> None:
        if state.move(delta):
            event.app.invalidate()

    def move_page(event, delta: int) -> None:
        if state.move_page(delta):
            event.app.invalidate()

    @bindings.add("up", eager=True)
    def _up(event) -> None:
        move(event, -1)

    @bindings.add("down", eager=True)
    def _down(event) -> None:
        move(event, 1)

    @bindings.add("left", eager=True)
    @bindings.add("pageup", eager=True)
    def _previous_page(event) -> None:
        move_page(event, -1)

    @bindings.add("right", eager=True)
    @bindings.add("pagedown", eager=True)
    def _next_page(event) -> None:
        move_page(event, 1)

    @bindings.add("home", eager=True)
    def _first(event) -> None:
        if state.move_to_boundary(end=False):
            event.app.invalidate()

    @bindings.add("end", eager=True)
    def _last(event) -> None:
        if state.move_to_boundary(end=True):
            event.app.invalidate()

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    @bindings.add("q", eager=True)
    def _close(event) -> None:
        event.app.exit(result=state.selected_index)

    def render_rows() -> StyleAndTextTuples:
        fragments: StyleAndTextTuples = []
        focus_style = focused_control_style(focused=True, selected=True)
        for position, index in enumerate(state.visible_indices):
            if index == state.selected_index:
                fragments.append(("[SetCursorPosition]", ""))
            for style, value, *_ in renderer.row(index):
                fragments.append(
                    ((f"{style} {focus_style}" if style else focus_style), value)
                    if index == state.selected_index
                    else (style, value)
                )
            if position < (state.page_stop - state.page_start - 1):
                fragments.append(("", "\n"))
        return fragments

    header = Window(
        FormattedTextControl(lambda: renderer.header(state)),
        height=Dimension.exact(renderer.header_height),
        wrap_lines=False,
    )
    rows = Window(
        FormattedTextControl(render_rows, focusable=True),
        height=Dimension.exact(renderer.row_window_height or renderer.page_size),
        # A result row is logically one Source record, but wrapping must retain
        # its complete content when that record is wider than the terminal.
        wrap_lines=True,
        always_hide_cursor=True,
    )
    footer = Window(
        FormattedTextControl([("class:report-neutral", renderer.footer)]),
        height=Dimension.exact(1),
        wrap_lines=False,
    )
    root = HSplit(
        (
            header,
            Window(height=Dimension.exact(1)),
            rows,
            Window(height=Dimension.exact(1)),
            footer,
        ),
        padding=0,
    )
    app: Application[int] = Application(
        layout=Layout(root, focused_element=rows),
        key_bindings=bindings,
        full_screen=False,
        # The final page is the command's result receipt, so leave it above the
        # next shell prompt instead of erasing it like a transient dialog.
        erase_when_done=False,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        input=app_input,
        output=app_output,
    )
    return app.run()
