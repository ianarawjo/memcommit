"""Context-targeted E-to-edit terminal workbench for Add."""

from __future__ import annotations

import json
from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.application.operations.create_copy_connect.add.application import (
    AddRequest,
    AddResult,
    AddSource,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
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
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.in_frame_input import (
    InFrameInputManager,
    InFrameInputSection,
)
from memcommit.adapters.console.terminal.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    build_scrollable_formatted_text_pane,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    bind_tui_interrupt,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.commands.create_copy_connect.add.workbench.model import (
    AddDraftState,
    AddWorkbenchSetup,
)


def _draft_fragments(
    state: AddDraftState,
    *,
    saved: AddResult | None,
) -> tuple[list[tuple[str, str]], int]:
    fragments: list[tuple[str, str]] = []
    cursor_position = 0
    plain_length = 0
    for index, content in enumerate(state.drafts):
        if index:
            fragments.append(("", "\n"))
            plain_length += 1
        selected = index == state.cursor
        if selected:
            cursor_position = plain_length
        pointer = "›" if selected else " "
        if saved is not None and index < saved.count:
            status = f"SAVED {saved.memories[index].uid[:8]}"
        elif state.editing == index:
            status = "EDITING"
        elif content is None:
            status = "EMPTY · E EDIT"
        else:
            status = "DRAFT"
        heading = f"{pointer} {index + 1} · [{status}]\n"
        heading_style = "class:detail-card.focused" if selected else "class:detail-card"
        fragments.append((heading_style, heading))
        plain_length += len(heading)
        preview = (
            "  (empty draft)"
            if content is None
            else "  "
            + elide_terminal_text(
                single_line_terminal_text(safe_terminal_text(content)),
                140,
            )
        )
        fragments.append(("class:memory-object", preview))
        plain_length += len(preview)
    return fragments, cursor_position


def run_add_workbench(
    *,
    setup: AddWorkbenchSetup,
    execute: Callable[[AddRequest], AddResult],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> AddResult | None:
    """Review exact multiline drafts, then persist one atomic Add batch."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Add",
            snapshot_hint="Pass INFO, --memory, --input, or --paste outside a terminal.",
        )
    if not isinstance(setup, AddWorkbenchSetup):
        raise TypeError("Add workbench requires an AddWorkbenchSetup.")

    selector = ContextSelectorControl(
        ContextSelectorView(
            names=setup.names,
            selected=(setup.selected_context,),
            mode="SINGLE",
            label="TARGET · CAN ADD MEMORIES · * CURRENT",
            current_context=setup.current_context,
            selectable_names=setup.selectable_names,
            annotations=setup.annotations,
        ),
        height=min(8, max(3, len(setup.names))),
    )
    drafts = AddDraftState()
    draft_pane = build_scrollable_formatted_text_pane(
        "DRAFT MEMORIES · E EDIT · N NEW · D DELETE",
        height=Dimension(weight=1, min=10),
        style="class:viewer-body",
        frame_style="",
    )
    editor = build_framed_multiline_input(
        "EDITOR",
        buffer_name="add-draft-editor",
        height=Dimension(min=6, preferred=8, max=12),
    )
    input_manager = InFrameInputManager(draft_pane.pane)
    bindings = KeyBindings()
    result: AddResult | None = None
    status = {"value": ""}

    def refresh_drafts() -> None:
        fragments, cursor_position = _draft_fragments(drafts, saved=result)
        draft_pane.set_formatted_text(fragments, anchor="preserve")
        draft_pane.text_area.buffer.cursor_position = min(
            cursor_position,
            len(draft_pane.text_area.text),
        )

    refresh_drafts()

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        style = "class:memcommit.choice.active.focused" if focused else ""
        pointer = "›" if focused else " "
        target = safe_terminal_text(selector.selection.selected_name)
        if result is not None:
            return [
                ("class:report-label", "STATUS · SUCCESS\n"),
                (
                    "class:report-neutral",
                    f"SAVED · {result.count} "
                    f"{'MEMORY' if result.count == 1 else 'MEMORIES'} · "
                    "ONE CHECKPOINT\n"
                    f"TARGET · {safe_terminal_text(result.context_name)}\n"
                    f"CHECKPOINT · {result.checkpoint_uid[:8]}\n",
                ),
                (style, f"{pointer} CLOSE · ENTER"),
            ]
        if drafts.editing is not None:
            action = "FINISH OR CANCEL THE ACTIVE EDIT"
        elif drafts.ready_contents:
            count = len(drafts.ready_contents)
            action = f"ADD {count} {'MEMORY' if count == 1 else 'MEMORIES'} · ENTER"
        else:
            action = "MEMORY REQUIRED · E EDIT"
        return [
            (style, f"{pointer} {action}\n"),
            ("class:report-neutral", f"TARGET · {target}\n"),
            (
                "class:report-neutral",
                "DURABLE EFFECT · ONE ATOMIC CHECKPOINT · NO PROVIDER",
            ),
        ]

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension.exact(6),
    )

    header = Window(
        FormattedTextControl(
            " MEM ADD\n"
            " CREATE ONE OR MORE EXACT MULTILINE MEMORIES · REVIEW BEFORE SAVE"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if get_app().layout.has_focus(editor.text_area):
            return " Enter newline · Ctrl-S save draft · Esc cancel edit"
        if result is not None:
            return " Enter/Esc/Q close · saved"
        if get_app().layout.has_focus(selector.control):
            return (
                " ↑/↓ move/cross · ←/→ tree · Enter/Space select · "
                "Tab drafts · Esc cancel"
            )
        if get_app().layout.has_focus(draft_pane.text_area):
            return (
                " ↑/↓ draft/cross · E edit · N new · D delete · Tab next · Esc cancel"
            )
        return " Enter add batch · ↑ drafts · Tab target · Esc cancel"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(selector.frame),
        TuiRegion(draft_pane.container),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[AddResult | None] = Application(
        layout=Layout(root, focused_element=draft_pane.text_area),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_context(_event, delta: int) -> SurfaceMoveResult:
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def enter_context(delta: int) -> None:
        rows = selector.tree.visible_rows()
        selector.tree.selected_name = rows[0 if delta > 0 else -1].name

    def choose_context(_event) -> SurfaceActionResult:
        if result is not None:
            return "IGNORED"
        try:
            selector.choose_cursor()
        except ValueError as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def move_draft(_event, delta: int) -> SurfaceMoveResult:
        if drafts.move(delta):
            refresh_drafts()
            return "MOVED"
        return "BOUNDARY"

    def begin_edit(event, *, new: bool = False) -> None:
        nonlocal result
        if result is not None:
            return
        try:
            text = drafts.new() if new else drafts.begin_edit()
        except ValueError as error:
            status["value"] = str(error)
            return
        editor.text_area.text = text
        editor.text_area.buffer.cursor_position = len(text)
        input_manager.show(
            draft_pane.pane,
            InFrameInputSection(
                "EDITOR · CTRL-S SAVE DRAFT · ESC CANCEL",
                editor.text_area,
                height=Dimension(min=5, preferred=7, max=10),
            ),
        )
        status["value"] = ""
        refresh_drafts()
        event.app.layout.focus(editor.text_area)
        event.app.invalidate()

    def activate_draft(event) -> SurfaceActionResult:
        begin_edit(event)
        return "HANDLED"

    def submit(event) -> SurfaceActionResult:
        nonlocal result
        if result is not None:
            event.app.exit(result=result)
            return "HANDLED"
        if drafts.editing is not None:
            status["value"] = "Save or cancel the active draft edit first."
            return "HANDLED"
        contents = drafts.ready_contents
        if not contents:
            status["value"] = "Press E to enter at least one Memory."
            event.app.layout.focus(draft_pane.text_area)
            return "HANDLED"
        raw_text = json.dumps(contents, ensure_ascii=False, separators=(",", ":"))
        request = AddRequest(
            context_locator=selector.selection.selected_name,
            contents=contents,
            source=AddSource(
                mode="TUI_DRAFTS",
                kind="interactive-tui",
                parser="explicit-multiline-drafts-v1",
                raw_text=raw_text,
            ),
        )
        try:
            completed = execute(request)
            if not isinstance(completed, AddResult):
                raise TypeError("Add application returned an invalid result.")
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status["value"] = f"Add failed · {error}"
            return "HANDLED"
        result = completed
        status["value"] = ""
        refresh_drafts()
        event.app.layout.focus(todo_control)
        return "HANDLED"

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "TARGET",
                selector.control,
                move_vertical=move_context,
                activate=choose_context,
                on_vertical_enter=enter_context,
            ),
            FocusSurface(
                "DRAFTS",
                draft_pane.text_area,
                move_vertical=move_draft,
                activate=activate_draft,
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

    selector_focus = has_focus(selector.control)

    @bindings.add("left", filter=selector_focus, eager=True)
    def _collapse(event) -> None:
        selector.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=selector_focus, eager=True)
    def _expand(event) -> None:
        selector.expand()
        event.app.invalidate()

    @bindings.add(" ", filter=selector_focus, eager=True)
    def _choose(event) -> None:
        choose_context(event)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "a", filter=selector_focus)
    def _expand_all(event) -> None:
        selector.toggle_expand_all()
        event.app.invalidate()

    drafts_focus = has_focus(draft_pane.text_area) & Condition(lambda: result is None)

    @bind_case_insensitive_key(bindings, "e", filter=drafts_focus)
    def _edit(event) -> None:
        begin_edit(event)

    @bind_case_insensitive_key(bindings, "n", filter=drafts_focus)
    def _new(event) -> None:
        begin_edit(event, new=True)

    @bind_case_insensitive_key(bindings, "d", filter=drafts_focus)
    def _delete(event) -> None:
        drafts.delete_selected()
        status["value"] = ""
        refresh_drafts()
        event.app.invalidate()

    @bindings.add("c-s", filter=has_focus(editor.text_area), eager=True)
    def _save_edit(event) -> None:
        try:
            drafts.save_edit(editor.text_area.text)
        except ValueError as error:
            status["value"] = str(error)
            event.app.invalidate()
            return
        input_manager.clear()
        status["value"] = "Draft saved locally · Context not changed."
        refresh_drafts()
        event.app.layout.focus(draft_pane.text_area)
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(editor.text_area), eager=True)
    def _cancel_edit(event) -> None:
        drafts.cancel_edit()
        input_manager.clear()
        status["value"] = "Edit cancelled · Context not changed."
        refresh_drafts()
        event.app.layout.focus(draft_pane.text_area)
        event.app.invalidate()

    read_only_focus = Condition(lambda: surfaces.active(get_app()) is not None)

    def close(event) -> None:
        event.app.exit(result=result)

    bind_tui_interrupt(bindings, close)

    @bindings.add("escape", filter=read_only_focus, eager=True)
    @bindings.add("backspace", filter=read_only_focus, eager=True)
    @bind_case_insensitive_key(bindings, "q", filter=read_only_focus)
    def _close(event) -> None:
        dispatch_tui_back(event, close=close)

    return app.run()
