"""Read-only History screen assembled from the shared Items/Viewer controls."""

from __future__ import annotations

from collections.abc import Sequence

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.terminal.components.focus import (
    SurfaceActionResult,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.history.controls import (
    HistoryControls,
    validate_history_screen,
)
from memcommit.adapters.console.terminal.components.history.model import (
    HISTORY_BACK,
    HistoryBackNavigation,
    HistoryDetailRenderer,
    HistoryPickerItem,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
)


def choose_history(
    entries: Sequence[HistoryPickerItem],
    *,
    context_name: str,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    initial_details_open: bool | None = None,
    detail_renderer: HistoryDetailRenderer | None = None,
    empty_message: str | None = None,
    empty_detail: str | None = None,
    back_navigation: bool = False,
    title: str | None = None,
    workbench_navigation: SessionWorkbenchNavigation | None = None,
) -> HistoryBackNavigation | None:
    """Inspect frozen history; Enter opens detail and never approves an operation."""

    validate_history_screen(context_name, title=title, require_tty=require_tty)
    history = HistoryControls(
        entries,
        initial_details_open=initial_details_open,
        detail_renderer=detail_renderer,
        empty_message=empty_message,
        empty_detail=empty_detail,
        navigation=workbench_navigation,
    )
    bindings = KeyBindings()

    def back_items(event) -> SurfaceActionResult:
        event.app.exit(result=HISTORY_BACK if back_navigation else None)
        return "HANDLED"

    bind_surface_navigation(
        bindings,
        SurfaceFocusController(history.surfaces(back_items=back_items)),
        back=True,
    )
    history.bind_viewer_keys(bindings)

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("c-c", eager=True)
    def cancel(event) -> None:
        event.app.exit(result=None)

    def footer() -> str:
        close = (
            "Esc/Backspace back  q close"
            if back_navigation
            else "Esc/Backspace/q close"
        )
        if not history.options:
            return f" {close}  ·  0/0"
        return history.viewer_footer() or (
            " FOCUS ITEMS · ↑/↓ move  Enter viewer  Tab switch  "
            f"{close}  ·  {history.position}"
        )

    header = Window(
        FormattedTextControl(
            f" {display_escape_text(title or 'HISTORY')} · {display_escape_text(context_name)}"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    footer_window = Window(
        FormattedTextControl(footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[HistoryBackNavigation | None] = Application(
        layout=Layout(
            build_tui_frame(
                *(
                    TuiRegion(frame)
                    for frame in (header, *history.frames, footer_window)
                )
            ),
            focused_element=history.list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
