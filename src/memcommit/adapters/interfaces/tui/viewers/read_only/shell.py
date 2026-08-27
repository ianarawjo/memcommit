"""Full-screen wrapper for already-rendered read-only reports."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.interfaces.console.terminal import is_interactive_terminal
from memcommit.adapters.interfaces.tui.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.adapters.interfaces.tui.components.scrollable_pane import (
    build_scrollable_formatted_text_pane,
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.adapters.interfaces.tui.core.keybindings import bind_case_insensitive_key
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)


def interactive_report_terminal() -> bool:
    """Return whether a report may replace stdout with a full-screen Viewer."""

    return is_interactive_terminal()


def run_read_only_viewer(
    text: str | StyleAndTextTuples,
    *,
    title: str,
    frame_title: str = "VIEWER",
    compact_height: int | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> None:
    """Show a report in the shared framed, wrapped, scrollable Viewer.

    ``compact_height`` bounds short inspection reports in the ordinary terminal
    buffer. It changes no navigation, read-only, or semantic-style behavior.
    """

    if require_tty and not interactive_report_terminal():
        raise ValueError("Interactive report Viewer requires a terminal.")
    if not isinstance(frame_title, str) or not frame_title or "\n" in frame_title:
        raise ValueError("Read-only Viewer frame title must be one non-empty line.")
    if compact_height is not None and (
        not isinstance(compact_height, int)
        or isinstance(compact_height, bool)
        or compact_height < 6
    ):
        raise ValueError("Compact report Viewer height must be at least 6 rows.")

    # The formatted pane keeps one shared cursor-backed scrolling contract for
    # both neutral reports and semantic documents. A plain string remains a
    # valid projection, so callers do not need a parallel Viewer shell merely
    # to add trusted semantic color tokens.
    pane = build_scrollable_formatted_text_pane(
        frame_title,
        text,
        height=(
            Dimension.exact(compact_height - 1)
            if compact_height is not None
            else Dimension(min=4, weight=1)
        ),
    )
    footer = Window(
        FormattedTextControl(
            f" {title} · ↑/↓ scroll · PgUp/PgDn page · "
            "Home/End · Esc/Backspace/Q close · read-only"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    bindings = KeyBindings()

    @bindings.add("up")
    def _up(event) -> None:
        move_wrapped_read_cursor(event, direction=-1)

    @bindings.add("down")
    def _down(event) -> None:
        move_wrapped_read_cursor(event, direction=1)

    @bindings.add("pageup")
    def _page_up(event) -> None:
        scroll_wrapped_page(event, direction=-1)

    @bindings.add("pagedown")
    def _page_down(event) -> None:
        scroll_wrapped_page(event, direction=1)

    @bindings.add("home")
    def _home(event) -> None:
        event.current_buffer.cursor_position = 0

    @bindings.add("end")
    def _end(event) -> None:
        event.current_buffer.cursor_position = len(event.current_buffer.text)

    def close(event) -> None:
        event.app.exit()

    for key in ("escape", "backspace", "c-c"):
        bindings.add(key)(close)
    bind_case_insensitive_key(bindings, "q")(close)

    root = build_tui_frame(TuiRegion(pane.container), TuiRegion(footer))
    if compact_height is not None:
        # A compact report preserves the same Viewer and scrolling mechanics;
        # only the bounded non-alternate-screen presentation differs.
        root.height = Dimension.exact(compact_height)
    app: Application[None] = Application(
        layout=Layout(
            root,
            focused_element=pane.text_area,
        ),
        key_bindings=bindings,
        full_screen=compact_height is None,
        erase_when_done=True,
        mouse_support=False,
        input=app_input,
        output=app_output,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    bind_focused_frame_style(
        pane.frame,
        is_focused=lambda: app.layout.has_focus(pane.text_area),
    )
    try:
        app.run()
    except (EOFError, KeyboardInterrupt):
        return
