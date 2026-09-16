"""Interactive direct-Memory selection and exact replacement workbench."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.direct_memory_selector import (
    DirectMemorySelectorControl,
    DirectMemorySelectorView,
)
from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
)
from memcommit.application.operations.edit.application import (
    EditRequest,
    FrozenEditPlan,
    validate_edit_request,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.action import build_action_control
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_tui_interrupt,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.commands.edit.workbench.model import EditTuiSetup


def run_edit_tui(
    setup: EditTuiSetup,
    *,
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]],
    content_loader: Callable[[DirectMemoryTarget], str],
    prepare: Callable[[EditRequest], FrozenEditPlan],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenEditPlan | None:
    if require_tty:
        require_interactive_terminal(
            "Interactive Edit",
            snapshot_hint=(
                "Pass MEMORY_SELECTOR CONTENT and optionally --context "
                "CONTEXT outside a terminal."
            ),
        )
    if not isinstance(setup, EditTuiSetup):
        raise TypeError("Edit TUI requires an EditTuiSetup.")

    source = DirectMemorySelectorControl(
        DirectMemorySelectorView(
            names=setup.names,
            selected_context=setup.selected_context,
            label="MEMORY · DIRECTLY OWNED · EDITABLE · * CURRENT",
            current_context=setup.current_context,
            selectable_names=setup.selectable_names,
            annotations=setup.annotations,
        ),
        memory_loader=memory_loader,
        height=min(10, max(4, len(setup.names) + 2)),
    )
    editor = build_framed_multiline_input(
        "REPLACEMENT CONTENT",
        buffer_name="edit-replacement-content",
        height=Dimension(min=7, preferred=9, max=12),
    )
    bindings = KeyBindings()
    status = {"value": "Select one direct Memory before editing its content."}

    def selected_request() -> EditRequest:
        target = source.selected
        if target is None:
            raise ValueError("Select one directly owned Memory first.")
        return EditRequest(
            memory_selector=target.memory_uid,
            content=editor.text_area.text,
            context_locator=target.context_name,
        )

    def describe_apply() -> str:
        target = source.selected
        if target is None:
            return "Select one directly owned Memory."
        return f"Save the replacement for Memory [{target.memory_uid[:8]}] in {target.context_name}."

    action_control = build_action_control("Apply", describe=describe_apply)
    action_line = Window(
        action_control, height=Dimension.exact(2), dont_extend_height=True
    )

    def content_changed(_buffer) -> None:
        status["value"] = ""

    editor.text_area.buffer.on_text_changed += content_changed
    header = Window(
        FormattedTextControl(
            " MEM EDIT · EXACT DIRECT MEMORY\n"
            " SELECT ONE MEMORY, EDIT ITS MULTILINE CONTENT, THEN APPLY"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def footer_text() -> str:
        if status["value"]:
            return " " + display_escape_text(status["value"])
        if get_app().layout.has_focus(source.control):
            return (
                " ↑/↓ move · ←/→ expand · Enter choose direct Memory · "
                "Tab content · Esc cancel"
            )
        if get_app().layout.has_focus(editor.text_area):
            return " Enter newline · Tab Apply · Shift-Tab Memory · Esc cancel"
        return " Enter Apply · Tab Memory · Esc cancel"

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(source.frame),
        TuiRegion(editor.frame),
        TuiRegion(action_line),
        TuiRegion(footer),
    )
    app: Application[FrozenEditPlan | None] = Application(
        layout=Layout(root, focused_element=source.control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def choose_source(_event) -> SurfaceActionResult:
        try:
            changed = source.choose_cursor()
            target = source.selected
            if target is not None and changed:
                content = content_loader(target)
                if not isinstance(content, str):
                    raise TypeError("Edit content loader returned a non-text value.")
                editor.text_area.text = content
                editor.text_area.buffer.cursor_position = len(content)
        except (
            FileNotFoundError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            status["value"] = str(error)
        else:
            status["value"] = "Memory selected · edit the replacement below."
        return "HANDLED"

    def finish(event) -> SurfaceActionResult:
        try:
            request = validate_edit_request(selected_request())
            frozen = prepare(request)
            # Approval binds the exact visible owner and Memory, even if a
            # future prepare adapter introduces name/selector normalization.
            if (frozen.context_name, frozen.memory_uid) != (
                request.context_locator,
                request.memory_selector,
            ):
                raise RuntimeError("The selected Edit Memory changed before Apply.")
        except (
            FileNotFoundError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(result=frozen)
        return "HANDLED"

    def clear_status() -> None:
        status["value"] = ""

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "MEMORY",
                source.control,
                move_vertical=lambda _event, delta: (
                    "MOVED" if source.move(delta) else "BOUNDARY"
                ),
                activate=choose_source,
            ),
            # Writable content retains ordinary Enter, arrows, and Backspace;
            # the shared controller owns only cross-frame Tab traversal here.
            FocusSurface("CONTENT", editor.text_area, on_focus=clear_status),
            FocusSurface(
                "APPLY",
                action_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=finish,
            ),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    source_focus = Condition(lambda: get_app().layout.has_focus(source.control))

    @bindings.add("left", filter=source_focus, eager=True)
    def _collapse_source(event) -> None:
        source.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=source_focus, eager=True)
    def _expand_source(event) -> None:
        source.expand()
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    def _cancel(event) -> None:
        dispatch_tui_back(event, close=lambda current: current.app.exit(result=None))

    bind_tui_interrupt(
        bindings,
        lambda event: event.app.exit(result=None),
    )

    return app.run()


__all__ = [
    "run_edit_tui",
]
