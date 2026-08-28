"""Read-only interactive viewer for one physical Ground workspace subtree."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.core.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.application.operations.ground.workspace_model import GroundWorkspace
from memcommit.adapters.console.terminal.core.capabilities import require_interactive_terminal
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    build_scrollable_formatted_text_pane,
)
from memcommit.adapters.console.terminal.core.keybindings import bind_case_insensitive_key
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import MEMCOMMIT_TUI_STYLE
from memcommit.adapters.console.commands.ground.workspace.viewer.model import (
    GroundWorkspaceViewerResult,
)


def _context_fragments(context: Context) -> list[tuple[str, str]]:
    items = tuple(context.iter_items())
    fragments: list[tuple[str, str]] = [
        ("class:memcommit.heading", safe_terminal_text(context.name)),
        ("", f"\nUID · {safe_terminal_text(context.uid)}"),
        ("", f"\nDIRECT ITEMS · {len(items)}"),
    ]
    if not items:
        fragments.extend((("", "\n\n"), ("class:viewer-muted", "(empty)")))
        return fragments
    for item in items:
        fragments.append(("", "\n\n"))
        fragments.append(("class:viewer-muted", f"[{item.uid[:8]}] "))
        if isinstance(item, MemoryRef):
            fragments.append(("class:memory", "MEMORY REF"))
            fragments.append(
                (
                    "",
                    "\n"
                    + safe_terminal_text(item.target_context_name)
                    + " · ["
                    + safe_terminal_text(item.target_memory_uid[:8])
                    + "]",
                )
            )
            if item.target is not None:
                fragments.append(
                    ("class:memory", "\n" + safe_terminal_text(item.target.content))
                )
        elif isinstance(item, QueryContextRef):
            fragments.append(("", "QUERY CONTEXT"))
            fragments.append(("", "\n" + safe_terminal_text(item.name)))
        elif isinstance(item, Context):
            fragments.append(("", "CONTEXT"))
            fragments.append(("", "\n" + safe_terminal_text(item.name)))
        else:
            assert isinstance(item, Memory)
            fragments.append(("class:memory", "MEMORY"))
            fragments.append(("class:memory", "\n" + safe_terminal_text(item.content)))
    return fragments


def run_ground_workspace_viewer(
    workspace: GroundWorkspace,
    *,
    navigation_contexts: tuple[Context, ...] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> GroundWorkspaceViewerResult:
    """Browse physical workspace Contexts without changing global current."""

    if require_tty:
        require_interactive_terminal("Interactive Ground workspace")
    visible_contexts = navigation_contexts or workspace.all_contexts
    contexts = {context.name: context for context in visible_contexts}
    required_names = {context.name for context in workspace.all_contexts}
    if not required_names.issubset(contexts):
        raise ValueError("Ground workspace navigation omitted a fixed Context.")
    names = tuple(context.name for context in visible_contexts)
    selected_name = workspace.goals.name
    selector = ContextSelectorControl(
        ContextSelectorView(
            names=names,
            selected=(selected_name,),
            mode="SINGLE",
            label="GROUND WORKSPACE · PHYSICAL CONTEXTS",
        ),
        height=len(names),
    )
    detail = build_scrollable_formatted_text_pane(
        "MEMORIES",
        _context_fragments(contexts[selected_name]),
        height=Dimension(weight=1),
        wrap_lines=True,
    )
    bindings = KeyBindings()

    header = Window(
        FormattedTextControl(
            " MEM GROUND · "
            + safe_terminal_text(workspace.name)
            + "\n CONTEXT-ROOTED WORKSPACE · "
            + safe_terminal_text(workspace.manifest.status)
            + " · REVISION "
            + str(workspace.manifest.revision)
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def footer_text() -> str:
        if get_app().layout.has_focus(selector.control):
            return (
                " ↑/↓ move/cross · ←/→ collapse/expand · Enter open · "
                "Tab Memories · Esc/Backspace/Q close · global current unchanged"
            )
        return (
            " ↑/↓ read/cross · PgUp/PgDn page · Home/End · Tab Contexts · "
            "Esc/Backspace/Q close · read-only"
        )

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(selector.frame),
        TuiRegion(detail.container),
        TuiRegion(footer),
    )
    app: Application[GroundWorkspaceViewerResult] = Application(
        layout=Layout(root, focused_element=selector.control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE]),
    )

    def move_context(_event, delta: int) -> SurfaceMoveResult:
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def open_context(_event) -> SurfaceActionResult:
        selector.choose_cursor()
        chosen = selector.selection.selected_name
        detail.set_formatted_text(_context_fragments(contexts[chosen]), anchor="start")
        get_app().layout.focus(detail.text_area)
        return "HANDLED"

    def move_detail(_event, delta: int) -> SurfaceMoveResult:
        buffer = detail.text_area.buffer
        before = buffer.cursor_position
        if delta > 0:
            buffer.cursor_down()
        else:
            buffer.cursor_up()
        return "MOVED" if buffer.cursor_position != before else "BOUNDARY"

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "contexts",
                selector.control,
                move_vertical=move_context,
                activate=open_context,
            ),
            FocusSurface(
                "memories",
                detail.text_area,
                move_vertical=move_detail,
            ),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    selector_focused = Condition(lambda: get_app().layout.has_focus(selector.control))
    detail_focused = Condition(lambda: get_app().layout.has_focus(detail.text_area))

    @bindings.add("right", filter=selector_focused)
    def _expand(event) -> None:
        selector.expand()
        event.app.invalidate()

    @bindings.add("left", filter=selector_focused)
    def _collapse(event) -> None:
        selector.collapse()
        event.app.invalidate()

    @bindings.add("pagedown", filter=detail_focused)
    def _page_down(event) -> None:
        detail.text_area.buffer.cursor_down(count=8)
        event.app.invalidate()

    @bindings.add("pageup", filter=detail_focused)
    def _page_up(event) -> None:
        detail.text_area.buffer.cursor_up(count=8)
        event.app.invalidate()

    @bindings.add("home", filter=detail_focused)
    def _home(event) -> None:
        detail.text_area.buffer.cursor_position = 0
        event.app.invalidate()

    @bindings.add("end", filter=detail_focused)
    def _end(event) -> None:
        detail.text_area.buffer.cursor_position = len(detail.text_area.text)
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    @bindings.add("c-c", eager=True)
    @bind_case_insensitive_key(bindings, "q", eager=True)
    def _close(event) -> None:
        event.app.exit(
            result=GroundWorkspaceViewerResult(
                context_name=selector.selection.selected_name,
            )
        )

    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return GroundWorkspaceViewerResult(
            context_name=selector.selection.selected_name,
        )


__all__ = ["run_ground_workspace_viewer"]
