"""Shared Context, reach, and semantic-result terminal workbench."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.context_targeting.tui.reach import (
    ContextReachState,
    ContextReachViewState,
    render_context_reach,
)
from memcommit.context_targeting.tui.picker import (
    ContextMemoryPreviewController,
    memory_visibility_key_hint,
)
from memcommit.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorRowProjection,
    ContextSelectorView,
)
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.viewers.semantic.controller import (
    SemanticViewerController,
)
from memcommit.interfaces.tui.workbenches.context_summary.model import (
    ContextSummaryWorkbenchReceipt,
    ContextSummaryWorkbenchView,
)
from memcommit.application.reviewing.session_navigation import SessionWorkbenchNavigation


def run_context_summary_workbench(
    view: ContextSummaryWorkbenchView,
    *,
    clipboard_projector: Callable[[str | None, bool], tuple[str, str]] | None = None,
    clipboard_writer: Callable[[str], None] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ContextSummaryWorkbenchReceipt | None:
    """Stage one Context and reach without executing operation semantics."""

    if require_tty:
        require_interactive_terminal(f"Interactive {view.operation_label.title()}")

    selector = ContextSelectorControl(
        ContextSelectorView(
            names=view.names,
            selected=(view.selected_context,),
            mode="SINGLE",
            label=(
                "CONTEXT · ALL READABLE CONTEXTS · * CURRENT"
                if view.targeting_editable
                else "SOURCE CONTEXT"
            ),
            current_context=view.current_context,
            annotations=view.annotations,
        ),
        height=min(9, max(3, len(view.names))),
    )
    memory_preview = (
        None
        if view.memory_loader is None
        else ContextMemoryPreviewController(selector.tree, view.memory_loader)
    )

    def project_context_row(row, focused) -> ContextSelectorRowProjection:
        memory_focused = (
            memory_preview is not None
            and memory_preview.memory_anchor is not None
            and memory_preview.memory_anchor[0] == row.name
        )
        return ContextSelectorRowProjection(
            branch=(None if memory_preview is None else memory_preview.branch_for(row)),
            nested_fragments=(
                ()
                if memory_preview is None
                else memory_preview.render_nested(
                    row,
                    wrap_width=max(1, get_app().output.get_size().columns - 8),
                )
            ),
            # A frozen Source may still receive read-only focus so its exact
            # item preview remains inspectable without becoming retargetable.
            show_context_cursor=(
                (view.targeting_editable or focused)
                and not (focused and memory_focused)
            ),
        )

    if memory_preview is not None or not view.targeting_editable:
        selector.row_projector = project_context_row
    reach = (
        ContextReachViewState.create(mode=view.range_mode)
        if view.allow_both
        else ContextReachState.create(
            include_descendants=view.range_mode == "SUBTREE"
        )
    )
    document = view.document
    navigation = SessionWorkbenchNavigation(pane="viewer")
    viewer = SemanticViewerController(navigation)
    bindings = KeyBindings()
    copy_receipt: tuple[bool, str] | None = None

    range_control: FormattedTextControl
    range_control = FormattedTextControl(
        lambda: (
            render_context_reach(
                reach,
                focused=get_app().layout.has_focus(range_control),
                title="RANGE",
            )
            if view.targeting_editable
            else [
                ("", " RANGE · "),
                ("class:memcommit.choice.selected", "[ THIS CONTEXT ONLY ]"),
            ]
        ),
        focusable=view.targeting_editable,
        show_cursor=False,
    )
    range_frame = build_focused_frame(
        Window(range_control, wrap_lines=False),
        title=("DESCENDANTS" if view.targeting_editable else "REACH"),
        is_focused=lambda: get_app().layout.has_focus(range_control),
        height=Dimension.exact(3),
    )

    def render_summary() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(summary_control)
        if document is None:
            style = "class:memcommit.choice.active.focused" if focused else ""
            pointer = "›" if focused else " "
            cursor = [('[SetCursorPosition]', '')] if focused else []
            return [
                *cursor,
                (style, f"{pointer} RUN {safe_terminal_text(view.operation_label.upper())} · ENTER\n"),
                (
                    "class:viewer-body",
                    f"  {safe_terminal_text(view.empty_message)}",
                ),
            ]
        return viewer.render(document, viewer_focused=focused)

    summary_control = FormattedTextControl(
        render_summary,
        focusable=True,
        show_cursor=False,
    )
    summary_frame = build_focused_frame(
        Window(
            summary_control,
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        ),
        title=safe_terminal_text(view.result_title),
        is_focused=lambda: get_app().layout.has_focus(summary_control),
        height=Dimension(weight=1),
    )

    header = Window(
        FormattedTextControl(
            f" MEM {safe_terminal_text(view.operation_label.upper())}\n"
            + (
                " PICK CONTEXT AND DESCENDANTS SEPARATELY"
                if view.targeting_editable
                else " SOURCE SELECTED"
            )
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        app = get_app()
        if app.layout.has_focus(selector.control):
            expansion = "A restore tree" if selector.tree.all_expanded else "A expand all"
            action = safe_terminal_text(view.operation_label.lower())
            memory_hint = (
                ""
                if memory_preview is None
                else memory_visibility_key_hint(selector.tree) + " · "
            )
            selection_hint = "Enter/Space select · " if view.targeting_editable else ""
            return (
                f" {memory_hint}↑/↓ move/cross · ←/→ collapse/expand · "
                f"{selection_hint}{expansion} · "
                f"Tab Summary · S {action} · Esc/Backspace/Q close"
            )
        if app.layout.has_focus(range_control):
            action = safe_terminal_text(view.operation_label.lower())
            return (
                " ←/→ direct or descendants · ↓ Context · Tab next · "
                f"S {action} · Esc/Backspace/Q close"
            )
        if app.layout.has_focus(summary_control):
            if document is None:
                navigation_hint = (
                    "↑ Context · Shift-Tab Context · "
                    if view.targeting_editable
                    else ""
                )
                return (
                    f" Enter run · {navigation_hint}"
                    "Esc/Backspace/Q close"
                )
            receipt = ""
            if copy_receipt is not None:
                succeeded, message = copy_receipt
                marker = "COPIED" if succeeded else "COPY FAILED"
                receipt = f" {marker} · {message} ·"
            return (
                f"{receipt} y current · Y all · ↑/↓ section/cross · "
                "PgUp/PgDn page · Home/End · S rerun · "
                "Esc/Backspace/Q close"
            )
        return " Esc/Backspace/Q close"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(range_frame),
        TuiRegion(selector.frame),
        TuiRegion(summary_frame),
        TuiRegion(footer),
    )
    initial_focus = (
        summary_control
        if document is not None or not view.targeting_editable
        else selector.control
    )
    app: Application[ContextSummaryWorkbenchReceipt | None] = Application(
        layout=Layout(root, focused_element=initial_focus),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def submit(event) -> SurfaceActionResult:
        event.app.exit(
            result=ContextSummaryWorkbenchReceipt(
                context_name=selector.selection.selected_name,
                range_mode=(
                    reach.mode
                    if isinstance(reach, ContextReachViewState)
                    else "SUBTREE"
                    if reach.include_descendants
                    else "EXACT"
                ),
            )
        )
        return "HANDLED"

    def move_context(_event, delta: int) -> SurfaceMoveResult:
        if memory_preview is not None:
            return "MOVED" if memory_preview.move(delta) else "BOUNDARY"
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def choose_context(_event) -> SurfaceActionResult:
        if not view.targeting_editable or (
            memory_preview is not None and memory_preview.memory_focused
        ):
            return "HANDLED"
        selector.choose_cursor()
        return "HANDLED"

    def enter_context(delta: int) -> None:
        rows = selector.tree.visible_rows()
        selector.tree.selected_name = rows[0 if delta > 0 else -1].name
        if memory_preview is not None:
            memory_preview.memory_anchor = None

    surfaces: SurfaceFocusController

    def move_range(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def advance_range(event) -> SurfaceActionResult:
        surfaces.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def move_summary(_event, delta: int) -> SurfaceMoveResult:
        nonlocal copy_receipt
        if document is None:
            return "BOUNDARY"
        copy_receipt = None
        before = navigation.section_uid
        viewer.move(document, delta)
        return "MOVED" if navigation.section_uid != before else "BOUNDARY"

    def advance_summary(event) -> SurfaceActionResult:
        surfaces.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def enter_summary(delta: int) -> None:
        if document is None:
            return
        if delta > 0:
            viewer.home(document)
        else:
            viewer.end(document)

    surface_values = []
    if view.targeting_editable:
        surface_values.append(
            FocusSurface(
                "DESCENDANTS",
                range_control,
                move_vertical=move_range,
                activate=advance_range,
            )
        )
    if view.targeting_editable or memory_preview is not None:
        surface_values.append(
            FocusSurface(
                "CONTEXT",
                selector.control,
                move_vertical=move_context,
                activate=choose_context,
                on_vertical_enter=enter_context,
            )
        )
    surface_values.append(
        FocusSurface(
            "SUMMARY",
            summary_control,
            move_vertical=move_summary,
            activate=submit if document is None else advance_summary,
            on_vertical_enter=None if document is None else enter_summary,
        )
    )
    surfaces = SurfaceFocusController(tuple(surface_values))
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("left", filter=has_focus(selector.control), eager=True)
    def _collapse(event) -> None:
        if memory_preview is None:
            selector.collapse()
        else:
            memory_preview.collapse_selected()
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(selector.control), eager=True)
    def _expand(event) -> None:
        if memory_preview is None:
            selector.expand()
        else:
            memory_preview.expand_selected()
        event.app.invalidate()

    @bindings.add(" ", filter=has_focus(selector.control), eager=True)
    def _choose(event) -> None:
        choose_context(event)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "a", filter=has_focus(selector.control))
    def _toggle_expand_all(event) -> None:
        if memory_preview is None:
            selector.toggle_expand_all()
        else:
            memory_preview.toggle_expand_all()
        event.app.invalidate()

    @bindings.add("m", filter=has_focus(selector.control), eager=True)
    def _toggle_selected_memories(event) -> None:
        if memory_preview is not None:
            memory_preview.toggle_selected_memories()
        event.app.invalidate()

    @bindings.add("M", filter=has_focus(selector.control), eager=True)
    def _toggle_all_memories(event) -> None:
        if memory_preview is not None:
            memory_preview.toggle_all_memories()
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(range_control), eager=True)
    def _range_left(event) -> None:
        reach.move(-1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(range_control), eager=True)
    def _range_right(event) -> None:
        reach.move(1)
        event.app.invalidate()

    def move_page(event, delta: int) -> None:
        if document is not None:
            viewer.move(document, delta)
            event.app.invalidate()

    @bindings.add("pageup", filter=has_focus(summary_control), eager=True)
    def _page_up(event) -> None:
        move_page(event, -8)

    @bindings.add("pagedown", filter=has_focus(summary_control), eager=True)
    def _page_down(event) -> None:
        move_page(event, 8)

    @bindings.add("home", filter=has_focus(summary_control), eager=True)
    def _home(event) -> None:
        if document is not None:
            viewer.home(document)
            event.app.invalidate()

    @bindings.add("end", filter=has_focus(summary_control), eager=True)
    def _end(event) -> None:
        if document is not None:
            viewer.end(document)
            event.app.invalidate()

    def copy_summary(event, *, whole_document: bool) -> None:
        nonlocal copy_receipt
        if (
            document is None
            or clipboard_projector is None
            or clipboard_writer is None
        ):
            copy_receipt = (False, "clipboard is unavailable")
            event.app.invalidate()
            return
        current = viewer.current(document)
        focused_uid = None if current is None else current.uid
        try:
            text, label = clipboard_projector(focused_uid, whole_document)
            if not text or not label:
                raise ValueError("the Summary has no text to copy")
            clipboard_writer(text)
        except (OSError, RuntimeError, ValueError) as error:
            copy_receipt = (False, safe_terminal_text(str(error)))
        else:
            # Read-only Summary copies never fabricate the structured stage
            # used by mutating clipboard operations.
            copy_receipt = (True, safe_terminal_text(label))
        event.app.invalidate()

    @bindings.add("y", filter=has_focus(summary_control), eager=True)
    def _copy_current(event) -> None:
        copy_summary(event, whole_document=False)

    @bindings.add("Y", filter=has_focus(summary_control), eager=True)
    def _copy_all(event) -> None:
        copy_summary(event, whole_document=True)

    @bind_case_insensitive_key(bindings, "s", eager=True)
    def _run(event) -> None:
        submit(event)

    def close(event) -> None:
        event.app.exit(result=None)

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
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
