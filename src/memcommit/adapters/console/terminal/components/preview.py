"""Scrollable exact-result Preview with operation-owned Apply."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
    bind_focused_frame_style,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.adapters.console.terminal.components.scrollable_pane.component import (
    build_scrollable_formatted_text_pane,
)
from memcommit.adapters.console.terminal.components.scrollable_pane.navigation import (
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerDocument,
)


def run_preview_screen(
    document: SemanticViewerDocument,
    *,
    operation: str,
    review_text: str = "",
    apply_preview: Callable,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
):
    """Read one exact document and apply through the operation-owned callback."""
    if require_tty:
        require_interactive_terminal(
            f"Interactive {operation} preview",
        )

    bindings = KeyBindings()
    result = None
    status = {"value": ""}
    last_error: dict[str, Exception | None] = {"value": None}

    # A result may contain many long Memories. Share Diff's wrapped line/page
    # navigation so reading never skips the middle of a section-sized block.
    viewer = build_scrollable_formatted_text_pane(
        "PREVIEW",
        document.render(focused_uid=None, viewer_focused=False),
        height=Dimension(min=4, weight=1),
    )
    viewer_control = viewer.text_area
    bind_focused_frame_style(
        viewer.frame,
        is_focused=lambda: get_app().layout.has_focus(viewer_control),
    )

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        cursor = [("[SetCursorPosition]", "")] if focused else []
        return [
            *([("class:report-neutral", review_text + "\n\n")] if review_text else []),
            *cursor,
            (focused_control_style(focused=focused), "[ APPLY ]"),
        ]

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · APPLY PREVIEW",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=lambda: Dimension.exact(
            review_text.count("\n") + 5 if review_text else 3
        ),
    )
    header = Window(
        FormattedTextControl(f" MEM {operation.upper()} · PREVIEW"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if get_app().layout.has_focus(viewer_control):
            return " ↑/↓ scroll · PgUp/PgDn · Home/End · Tab Apply · Esc cancel"
        return " Enter apply · ↑ Viewer · Tab Viewer · Esc cancel"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(viewer.container),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app = Application(
        layout=Layout(root, focused_element=viewer_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_viewer(event, delta: int) -> SurfaceMoveResult:
        return (
            "MOVED" if move_wrapped_read_cursor(event, direction=delta) else "BOUNDARY"
        )

    def submit(event) -> SurfaceActionResult:
        nonlocal result
        try:
            completed = apply_preview()
            if completed is None:
                raise TypeError(f"{operation} application returned no receipt.")
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status["value"] = f"{operation} failed · {error}"
            last_error["value"] = error
            return "HANDLED"
        # Keep a completed save reportable if terminal interruption races with exit.
        result = completed
        status["value"] = ""
        last_error["value"] = None
        event.app.exit(result=result)
        return "HANDLED"

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "VIEWER",
                viewer_control,
                move_vertical=move_viewer,
            ),
            FocusSurface(
                "TO_DO",
                todo_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=submit,
            ),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("home", eager=True)
    def _home(event) -> None:
        if event.app.layout.has_focus(viewer_control):
            viewer.text_area.buffer.cursor_position = 0
            event.app.invalidate()

    @bindings.add("end", eager=True)
    def _end(event) -> None:
        if event.app.layout.has_focus(viewer_control):
            viewer.text_area.buffer.cursor_position = len(viewer.text_area.text)
            event.app.invalidate()

    @bindings.add("pageup", eager=True)
    def _page_up(event) -> None:
        if event.app.layout.has_focus(viewer_control):
            scroll_wrapped_page(event, direction=-1)

    @bindings.add("pagedown", eager=True)
    def _page_down(event) -> None:
        if event.app.layout.has_focus(viewer_control):
            scroll_wrapped_page(event, direction=1)

    def close(event) -> None:
        event.app.exit(result=result)

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        dispatch_tui_back(event, close=close)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bind_case_insensitive_key(bindings, "q", eager=True)
    def _close(event) -> None:
        close(event)

    try:
        outcome = app.run()
    except (EOFError, KeyboardInterrupt):
        outcome = result
    if outcome is None and last_error["value"] is not None:
        raise RuntimeError(f"Interactive {operation} failed: {last_error['value']}")
    return outcome
