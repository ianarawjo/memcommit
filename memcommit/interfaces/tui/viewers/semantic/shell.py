"""Full-screen shell for one typed semantic Viewer document."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.interfaces.tui.core.keybindings import bind_case_insensitive_key
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.viewers.semantic.controller import (
    SemanticViewerController,
)
from memcommit.interfaces.tui.viewers.semantic.model import SemanticViewerDocument
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation
from prompt_toolkit.widgets import Frame


def run_semantic_viewer(
    document: SemanticViewerDocument,
    *,
    title: str,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SemanticViewerDocument:
    """Navigate one immutable semantic document without operation effects."""

    if require_tty:
        require_interactive_terminal("Semantic Viewer")
    if not isinstance(document, SemanticViewerDocument) or not document.sections:
        raise ValueError("Semantic Viewer requires a nonempty typed document.")

    navigation = SessionWorkbenchNavigation(pane="viewer")
    controller = SemanticViewerController(navigation)
    body_control = FormattedTextControl(
        lambda: controller.render(document),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    bindings = KeyBindings()

    def move(delta: int, event) -> None:
        controller.move(document, delta)
        event.app.invalidate()

    @bindings.add("down")
    def _down(event) -> None:
        move(1, event)

    @bindings.add("up")
    def _up(event) -> None:
        move(-1, event)

    @bindings.add("pagedown")
    def _page_down(event) -> None:
        move(8, event)

    @bindings.add("pageup")
    def _page_up(event) -> None:
        move(-8, event)

    @bindings.add("home")
    def _home(event) -> None:
        controller.home(document)
        event.app.invalidate()

    @bindings.add("end")
    def _end(event) -> None:
        controller.end(document)
        event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=document)

    for key in ("escape", "backspace", "c-c"):
        bindings.add(key)(close)
    bind_case_insensitive_key(bindings, "q")(close)

    footer = Window(
        FormattedTextControl(
            f" {title} · ↑/↓ section · PgUp/PgDn page · "
            "Home/End · Esc/Backspace/Q close · read-only"
        ),
        height=1,
        dont_extend_height=True,
    )
    viewer_frame = Frame(body, title="VIEWER")
    application: Application[SemanticViewerDocument] = Application(
        layout=Layout(
            build_tui_frame(
                TuiRegion(viewer_frame),
                TuiRegion(footer),
            ),
            focused_element=body_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        mouse_support=False,
        input=app_input,
        output=app_output,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    bind_focused_frame_style(
        viewer_frame,
        is_focused=lambda: application.layout.has_focus(body_control),
    )
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return document
