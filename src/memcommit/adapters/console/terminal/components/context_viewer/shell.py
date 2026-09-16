"""Compose the shared Context tree, read pane, and two-surface navigation."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_tui_frame,
    bind_focused_frame_style,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    build_scrollable_formatted_text_pane,
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)


def run_context_viewer(
    names: tuple[str, ...],
    render_context: Callable[[str, int], list[tuple[str, str]]],
    *,
    title: str = "CONTEXTS",
    folder_parents: bool = False,
    compact_names: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str:
    """Return the last locally opened name without invoking any store action."""
    if require_tty:
        require_interactive_terminal(title)
    if not names:
        raise ValueError("No Contexts are available to view.")
    selector = ContextSelectorControl(
        ContextSelectorView(
            names=names,
            selected=(names[0],),
            label=title,
            folder_parents=folder_parents,
            compact_names=compact_names,
        ),
        height=9,
    )
    detail = build_scrollable_formatted_text_pane(
        "VIEWER",
        "",
        height=Dimension(weight=1),
        wrap_lines=True,
    )
    bind_focused_frame_style(
        detail.frame, is_focused=lambda: app.layout.has_focus(detail.text_area)
    )
    bindings = KeyBindings()
    tree_focus = Condition(lambda: app.layout.has_focus(selector.control))
    viewer_focus = Condition(lambda: app.layout.has_focus(detail.text_area))

    def move_context(event, delta):
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if before != selector.tree.selected_name else "BOUNDARY"

    def show_context(name):
        width = max(1, app.output.get_size().columns - 4)
        detail.set_formatted_text(render_context(name, width), anchor="start")

    def open_context(event):
        name = selector.tree.selected_name
        if name not in selector.selectable:
            if name in selector.tree.expanded:
                selector.collapse()
            else:
                selector.expand()
            return "HANDLED"
        selector.choose_cursor()
        show_context(name)
        event.app.layout.focus(detail.text_area)
        return "HANDLED"

    def move_viewer(event, delta):
        return (
            "MOVED" if move_wrapped_read_cursor(event, direction=delta) else "BOUNDARY"
        )

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "contexts",
                selector.control,
                move_vertical=move_context,
                activate=open_context,
            ),
            FocusSurface("viewer", detail.text_area, move_vertical=move_viewer),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("right", filter=tree_focus)
    def expand(event):
        selector.expand()
        event.app.invalidate()

    @bindings.add("left", filter=tree_focus)
    def collapse(event):
        selector.collapse()
        event.app.invalidate()

    @bindings.add("left", filter=viewer_focus)
    @bindings.add("right", filter=viewer_focus)
    def ignore_horizontal_cursor(event):
        # Read-only TextArea still inherits character movement; consume it here.
        pass

    @bind_case_insensitive_key(bindings, "a", filter=tree_focus)
    def expand_all(event):
        selector.toggle_expand_all()
        event.app.invalidate()

    @bindings.add("pageup", filter=viewer_focus)
    def page_up(event):
        scroll_wrapped_page(event, direction=-1)

    @bindings.add("pagedown", filter=viewer_focus)
    def page_down(event):
        scroll_wrapped_page(event, direction=1)

    @bindings.add("home", filter=viewer_focus)
    def home(event):
        detail.text_area.buffer.cursor_position = 0

    @bindings.add("end", filter=viewer_focus)
    def end(event):
        detail.text_area.buffer.cursor_position = len(detail.text_area.text)

    def close(event):
        event.app.exit(result=selector.selection.selected_name)

    def back_to_tree(event):
        if event.app.layout.has_focus(detail.text_area):
            event.app.layout.focus(selector.control)
            return True
        return False

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def back(event):
        dispatch_tui_back(event, back_to_tree, close=close)

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("c-c", eager=True)
    def quit_viewer(event):
        close(event)

    footer = Window(
        FormattedTextControl(
            lambda: (
                " ↑↓ move · ←→ expand/collapse · Enter open · A expand all · Tab Viewer · Esc/Q close"
                if app.layout.has_focus(selector.control)
                else " ↑↓ read · PgUp/PgDn page · Home/End · Tab Contexts · Esc/Backspace back · Q close"
            )
        ),
        height=1,
    )
    app = Application(
        layout=Layout(
            build_tui_frame(
                TuiRegion(selector.frame),
                TuiRegion(detail.container),
                TuiRegion(footer),
            ),
            focused_element=selector.control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    try:
        return app.run(pre_run=lambda: show_context(names[0]))
    except (EOFError, KeyboardInterrupt):
        return selector.selection.selected_name
