"""Interactive direct-Memory selection and exact replacement editor."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.context_targeting.model import DirectMemoryTarget
from memcommit.context_targeting.tui.direct_memory_selector import (
    DirectMemorySelectorControl,
    DirectMemorySelectorView,
)
from memcommit.context_targeting.tui.picker import ContextMemoryRow
from memcommit.edit_application import (
    EditRequest,
    FrozenEditPlan,
    edit_target_selector,
    validate_edit_request,
)
from memcommit.exact_command_review import ExactCommandReview
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import (
    display_escape_text,
    restore_display_escape_text,
)
from memcommit.interfaces.tui.components.exact_command_review import (
    EditableExactCommandControl,
    ExactCommandDraft,
    ExactCommandForm,
    ExactCommandFormField,
    resolve_displayed_command_value,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.interfaces.tui.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.interfaces.tui.core.keybindings import dispatch_tui_back
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.operations.edit.model import EditTuiSetup


EDIT_COMMAND_FORM = ExactCommandForm(
    command=("mem", "edit"),
    usage="mem edit MEMORY_SELECTOR CONTENT --context CONTEXT",
    fields=(
        ExactCommandFormField(
            "MEMORY_SELECTOR",
            "one directly owned Memory UID or unambiguous prefix",
        ),
        ExactCommandFormField(
            "CONTENT",
            "exact replacement text using canonical single-line terminal escapes",
        ),
        ExactCommandFormField(
            "--context CONTEXT",
            "the exact UPDATE-authorized Context that owns the Memory",
        ),
    ),
)


def parse_edit_command_argv(argv: Sequence[str]) -> EditRequest:
    """Parse the editable exact Edit subset without invoking a nested CLI."""

    values = tuple(argv)
    if values[:2] != ("mem", "edit"):
        raise ValueError("Editable Edit commands must start with 'mem edit'.")
    if len(values) != 6:
        raise ValueError(
            "Editable Edit commands require MEMORY_SELECTOR CONTENT "
            "--context CONTEXT."
        )
    memory_selector, displayed_content, context_flag, context = values[2:]
    if context_flag not in {"--context", "-c"}:
        raise ValueError("Editable Edit commands require --context CONTEXT.")
    if not context:
        raise ValueError("Edit --context requires one Context value.")
    try:
        content = restore_display_escape_text(displayed_content)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Edit CONTENT is invalid: {error}") from error
    request = validate_edit_request(
        EditRequest(
            memory_selector=memory_selector,
            content=content,
            context_locator=context,
        )
    )
    # The editable projection always spells the owner separately so the
    # selector, Context, and checked row can synchronize without two grammars.
    edit_target_selector(request)
    return request


def edit_exact_command_review(request: EditRequest) -> ExactCommandReview:
    context = request.context_locator
    if context is None:
        raise ValueError("Edit review requires an exact Context.")
    return ExactCommandReview(
        argv=(
            "mem",
            "edit",
            request.memory_selector,
            request.content,
            "--context",
            context,
        ),
        effects=(
            f"Only Memory [{request.memory_selector[:8]}] in '{context}' may change.",
            "The Memory keeps its full UID and direct-item position.",
            "A changed value creates one Edit checkpoint; an unchanged value creates none.",
        ),
    )


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
            label="MEMORY · DIRECTLY OWNED · UPDATE AUTHORITY · * CURRENT",
            current_context=setup.current_context,
            selectable_names=setup.selectable_names,
            annotations=setup.annotations,
        ),
        memory_loader=memory_loader,
        height=min(10, max(4, len(setup.names) + 2)),
    )
    editor = build_framed_multiline_input(
        "REPLACEMENT CONTENT · NOT SAVED",
        buffer_name="edit-replacement-content",
        height=Dimension(min=7, preferred=9, max=12),
    )
    bindings = KeyBindings()
    status = {"value": "Select one direct Memory before editing its content."}
    synchronizing_from_command = {"value": False}

    def selected_request() -> EditRequest:
        target = source.selected
        if target is None:
            raise ValueError("Select one directly owned Memory first.")
        return EditRequest(
            memory_selector=target.memory_uid,
            content=editor.text_area.text,
            context_locator=target.context_name,
        )

    def apply_command_argv(argv: tuple[str, ...]) -> None:
        """Validate the whole command before moving process-local fields."""

        request = parse_edit_command_argv(argv)
        assert request.context_locator is not None
        context_name = resolve_displayed_command_value(
            request.context_locator,
            tuple(source.contexts.selectable),
            label="--context Context",
        )
        target = source.resolve_target(context_name, request.memory_selector)

        # Parsing, catalog lookup, and exact Memory resolution finish before
        # the selector and editor move together.  The guard prevents the lower
        # field update from rewriting a command while its buffer owns input.
        synchronizing_from_command["value"] = True
        try:
            source.select_target(target)
            editor.text_area.text = request.content
            editor.text_area.buffer.cursor_position = len(request.content)
        finally:
            synchronizing_from_command["value"] = False
        status["value"] = ""

    command_control = EditableExactCommandControl.create(
        ExactCommandDraft(
            review=lambda: edit_exact_command_review(selected_request()),
            apply_argv=apply_command_argv,
            form=EDIT_COMMAND_FORM,
        ),
        action_label="PRESS ENTER TO APPLY THE REVIEWED EDIT",
        incomplete_action="FIX THE RED COMMAND BEFORE APPLY",
        input_name="edit-proposed-command",
    )
    proposed_command_frame = build_focused_frame(
        command_control.body,
        title=lambda: (
            "PROPOSED COMMAND"
            if command_control.valid
            else "PROPOSED COMMAND · INVALID"
        ),
        is_focused=command_control.is_focused,
        height=Dimension.exact(4),
    )
    # Validity, rather than focus, is the complete color signal for this
    # editable approval boundary: invalid is red and runnable is blue.
    proposed_command_frame.container.style = command_control.frame_style

    def content_changed(_buffer) -> None:
        if synchronizing_from_command["value"]:
            return
        status["value"] = ""
        command_control.sync_from_review()

    editor.text_area.buffer.on_text_changed += content_changed
    header = Window(
        FormattedTextControl(
            " MEM EDIT · EXACT DIRECT MEMORY\n"
            " SELECT ONE MEMORY, EDIT ITS MULTILINE CONTENT, THEN REVIEW"
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
            return " Enter newline · Tab review · Shift-Tab Memory · Esc cancel"
        if not command_control.valid:
            return " FIX THE RED COMMAND BEFORE APPLY · Tab Memory · Esc cancel"
        return (
            " PRESS ENTER TO APPLY THE REVIEWED EDIT · "
            "Tab Memory · Esc cancel"
        )

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(source.frame),
        TuiRegion(editor.frame),
        TuiRegion(proposed_command_frame),
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
            status["value"] = "Memory selected · replacement is still process-local."
            command_control.sync_from_review()
        return "HANDLED"

    def finish(event) -> SurfaceActionResult:
        if not command_control.validate_current(event.app):
            status["value"] = "INVALID COMMAND · FIX THE RED EDITABLE FIELD"
            return "HANDLED"
        try:
            request = selected_request()
            expected = edit_exact_command_review(request)
            frozen = prepare(request)
            canonical_request = EditRequest(
                frozen.memory_uid,
                request.content,
                frozen.context_name,
            )
            if edit_exact_command_review(canonical_request) != expected:
                raise RuntimeError(
                    "The exact Edit command changed while it was reviewed."
                )
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
                "PROPOSED_COMMAND",
                command_control.active_control,
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

    return app.run()


__all__ = [
    "EDIT_COMMAND_FORM",
    "edit_exact_command_review",
    "parse_edit_command_argv",
    "run_edit_tui",
]
