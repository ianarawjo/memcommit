"""Interactive exact-command review for direct or recursive Merge."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.context_targeting.tui.reach import (
    ContextReachState,
    render_context_reach,
)
from memcommit.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
    render_exact_command_review,
)
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
    focused_control_style,
)
from memcommit.interfaces.tui.operations.merge.model import MergeTuiSetup
from memcommit.merge_application import (
    MergeError,
    MergeReach,
    MergeRequest,
    MergeResult,
)
from memcommit.merge_runtime import merge_summary


def merge_exact_command_review(
    source_name: str,
    target_name: str,
    *,
    recursive: bool,
) -> ExactCommandReview:
    """Describe one exact deterministic union and its complete reach boundary."""

    scope = (
        "matching lexical descendants by complete relative path"
        if recursive
        else "the two exact Context roots only"
    )
    target_effect = (
        f"Target subtree '{target_name}' may update existing matching Contexts "
        "and create Source-only relative paths."
        if recursive
        else f"Only direct items in Target Context '{target_name}' may change."
    )
    return ExactCommandReview(
        argv=(
            "mem",
            "merge",
            source_name,
            "--recursive" if recursive else "--direct",
        ),
        effects=(
            f"Merge {scope} into frozen current Target '{target_name}'.",
            target_effect,
            "Add UID-new direct items; keep Target values for existing UIDs.",
            "No semantic reconciliation and no deletion propagation.",
        ),
    )


def run_merge_tui(
    *,
    setup: MergeTuiSetup,
    execute: Callable[[MergeRequest], MergeResult],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MergeResult | None:
    """Select Source/reach and execute only the exact reviewed Merge."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Merge",
            snapshot_hint="Pass SOURCE with --direct or --recursive outside a terminal.",
        )
    if not isinstance(setup, MergeTuiSetup):
        raise TypeError("Merge TUI requires a MergeTuiSetup.")

    selector = ContextSelectorControl(
        ContextSelectorView(
            names=setup.names,
            selected=(setup.selected_source,),
            mode="SINGLE",
            label="SOURCE · ALL READABLE CONTEXTS · * CURRENT TARGET",
            current_context=setup.current_context,
            selectable_names=setup.selectable_names,
            annotations=setup.annotations,
        ),
        height=min(12, max(4, len(setup.names))),
    )
    reach = ContextReachState.create(
        include_descendants=setup.initial_recursive,
    )
    bindings = KeyBindings()
    result: MergeResult | None = None
    status = {"value": ""}
    last_error: dict[str, Exception | None] = {"value": None}

    range_control: FormattedTextControl
    range_control = FormattedTextControl(
        lambda: render_context_reach(
            reach,
            focused=get_app().layout.has_focus(range_control),
            title="RANGE",
        ),
        focusable=True,
        show_cursor=False,
    )
    range_frame = build_focused_frame(
        Window(range_control, wrap_lines=False),
        title="DESCENDANTS",
        is_focused=lambda: get_app().layout.has_focus(range_control),
        height=Dimension.exact(3),
    )

    def selected_review() -> ExactCommandReview:
        return merge_exact_command_review(
            selector.selection.selected_name,
            setup.target_context,
            recursive=reach.include_descendants,
        )

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        style = focused_control_style(focused=focused)
        cursor = [("[SetCursorPosition]", "")] if focused else []
        if result is None:
            return [
                (
                    "class:report-neutral",
                    render_exact_command_review(selected_review()),
                ),
                ("", "\n\n"),
                *cursor,
                (style, "[ PRESS ENTER TO APPLY THE EXACT MERGE ]"),
            ]
        created = sum(context.target_created for context in result.contexts)
        return [
            ("class:report-label", "STATUS · SUCCESS\n"),
            (
                "class:report-neutral",
                f"SOURCE · {safe_terminal_text(result.source_name)}\n"
                f"TARGET · {safe_terminal_text(result.target_name)}\n"
                f"RANGE · {result.reach.value}\n"
                f"CONTEXTS · {len(result.contexts)} · CREATED {created}\n"
                f"ADDED · {safe_terminal_text(merge_summary(result.additions))}\n"
                f"CHECKPOINTS · {len(result.checkpoint_uids)}\n\n",
            ),
            *cursor,
            (style, "[ PRESS ENTER TO CLOSE ]"),
        ]

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · EXACT COMMAND",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension(min=15, weight=1),
    )
    header = Window(
        FormattedTextControl(
            " MEM MERGE · SOURCE → CURRENT TARGET\n"
            " DETERMINISTIC UID UNION · DIRECT OR PATH-ALIGNED DESCENDANTS"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if result is not None:
            return " Enter/Esc/Q close · durable receipt shown above"
        if get_app().layout.has_focus(range_control):
            return " ←/→ direct or descendants · ↓ Source · Tab next · Esc cancel"
        if get_app().layout.has_focus(selector.control):
            return (
                " ↑/↓ move/cross · ←/→ tree · Enter/Space select · "
                "Tab exact review · Esc cancel"
            )
        return " Enter apply exact command · ↑ Source · Tab range · Esc cancel"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(range_frame),
        TuiRegion(selector.frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[MergeResult | None] = Application(
        layout=Layout(root, focused_element=selector.control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_selector(_event, delta: int) -> SurfaceMoveResult:
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def enter_selector(delta: int) -> None:
        rows = selector.tree.visible_rows()
        selector.tree.selected_name = rows[0 if delta > 0 else -1].name

    def choose_source(_event) -> SurfaceActionResult:
        if result is not None:
            return "IGNORED"
        try:
            selector.choose_cursor()
        except ValueError as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
            last_error["value"] = None
        return "HANDLED"

    def submit(event) -> SurfaceActionResult:
        nonlocal result
        if result is not None:
            event.app.exit(result=result)
            return "HANDLED"
        request = MergeRequest(
            source_locator=selector.selection.selected_name,
            reach=(
                MergeReach.DESCENDANTS
                if reach.include_descendants
                else MergeReach.DIRECT
            ),
        )
        try:
            completed = execute(request)
            if not isinstance(completed, MergeResult):
                raise TypeError("Merge application returned an invalid result.")
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status["value"] = f"Merge failed · {error}"
            last_error["value"] = error
            return "HANDLED"
        result = completed
        status["value"] = ""
        last_error["value"] = None
        event.app.layout.focus(todo_control)
        event.app.invalidate()
        return "HANDLED"

    surfaces: SurfaceFocusController

    def advance_range(event) -> SurfaceActionResult:
        surfaces.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "RANGE",
                range_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=advance_range,
            ),
            FocusSurface(
                "SOURCE",
                selector.control,
                move_vertical=move_selector,
                activate=choose_source,
                on_vertical_enter=enter_selector,
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

    @bindings.add("left", filter=has_focus(range_control), eager=True)
    def _range_left(event) -> None:
        reach.move(-1)
        status["value"] = ""
        last_error["value"] = None
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(range_control), eager=True)
    def _range_right(event) -> None:
        reach.move(1)
        status["value"] = ""
        last_error["value"] = None
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(selector.control), eager=True)
    def _collapse(event) -> None:
        selector.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(selector.control), eager=True)
    def _expand(event) -> None:
        selector.expand()
        event.app.invalidate()

    @bindings.add(" ", filter=has_focus(selector.control), eager=True)
    def _choose(event) -> None:
        choose_source(event)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "a", filter=has_focus(selector.control))
    def _toggle_expand_all(event) -> None:
        selector.toggle_expand_all()
        event.app.invalidate()

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
        raise MergeError(f"Interactive Merge failed: {last_error['value']}")
    return outcome
