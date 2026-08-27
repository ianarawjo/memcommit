"""Interactive immutable Memory or Context Reference setup."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.core.context_targeting.tui.direct_memory_selector import (
    DirectMemorySelectorControl,
    DirectMemorySelectorView,
)
from memcommit.core.context_targeting.tui.picker import ContextMemoryRow
from memcommit.core.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.application.exact_command_review import ExactCommandReview
from memcommit.adapters.interfaces.console.terminal import require_interactive_terminal
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.adapters.interfaces.tui.components.exact_command_review import (
    render_exact_command_review,
)
from memcommit.adapters.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.interfaces.tui.core.keybindings import (
    bind_tui_interrupt,
    dispatch_tui_back,
)
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.application.operations.reference.application import (
    ContextReferenceRequest,
    FrozenContextReferencePlan,
    FrozenReferencePlan,
    ReferenceRequest,
)
from memcommit.adapters.interfaces.tui.operations.reference.model import ReferenceTuiSetup


def reference_exact_command_review(request: ReferenceRequest) -> ExactCommandReview:
    target = request.into_locator
    if target is None:
        raise ValueError("Reference review requires an exact Target Context.")
    return ExactCommandReview(
        argv=(
            "mem",
            "reference",
            request.memory_selector,
            "--from",
            request.source_locator,
            "--into",
            target,
        ),
        effects=(
            f"Only Context '{target}' changes.",
            (
                f"Memory [{request.memory_selector[:8]}] remains owned by "
                f"'{request.source_locator}'; the Target retains this exact version."
            ),
            "The new snapshot is read-only and does not follow later Source edits.",
        ),
    )


def context_reference_exact_command_review(
    request: ContextReferenceRequest,
) -> ExactCommandReview:
    """Build one exact direct/recursive Context snapshot command."""

    target = request.into_locator
    if target is None:
        raise ValueError("Reference review requires an exact Target Context.")
    scope = "--recursive" if request.include_descendants else "--direct"
    scope_text = (
        "lexical descendants and local embedded Context contents"
        if request.include_descendants
        else "only the Source Context's direct contents; embedded rows stay opaque"
    )
    return ExactCommandReview(
        argv=(
            "mem",
            "reference",
            request.source_locator,
            "--into",
            target,
            scope,
        ),
        effects=(
            f"Only Context '{target}' changes.",
            (
                f"Context '{request.source_locator}' remains independently owned; "
                f"the Target retains {scope_text}."
            ),
            "The new snapshot is read-only and does not follow later Source edits.",
        ),
    )


def run_reference_tui(
    setup: ReferenceTuiSetup,
    *,
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]],
    prepare: Callable[[ReferenceRequest], FrozenReferencePlan],
    prepare_context: Callable[
        [ContextReferenceRequest],
        FrozenContextReferencePlan,
    ],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenReferencePlan | FrozenContextReferencePlan | None:
    if require_tty:
        require_interactive_terminal(
            "Interactive Reference",
            snapshot_hint=(
                "Pass SOURCE_CONTEXT [-d|-r], or MEMORY_SELECTOR --from "
                "SOURCE_CONTEXT, and optionally --into TARGET_CONTEXT outside "
                "a terminal."
            ),
        )
    if not isinstance(setup, ReferenceTuiSetup):
        raise TypeError("Reference TUI requires a ReferenceTuiSetup.")

    memory_source = DirectMemorySelectorControl(
        DirectMemorySelectorView(
            names=setup.memory_source_names,
            selected_context=setup.selected_memory_source,
            label="SOURCE MEMORY · OWNED OR GRANTED FOR RETAINED REFERENCE",
            current_context=setup.current_context,
            selectable_names=setup.memory_source_selectable_names,
            annotations=setup.memory_source_annotations,
        ),
        memory_loader=memory_loader,
        height=min(10, max(4, len(setup.memory_source_names) + 2)),
    )
    context_source = ContextSelectorControl(
        ContextSelectorView(
            names=setup.context_source_names,
            selected=(setup.selected_source,),
            label="SOURCE CONTEXT · SNAPSHOT THIS SCOPE · * CURRENT",
            current_context=setup.current_context,
        ),
        height=min(8, max(3, len(setup.context_source_names))),
    )
    target = ContextSelectorControl(
        ContextSelectorView(
            names=setup.target_names,
            selected=(setup.selected_target,),
            label="TARGET · ADD IMMUTABLE SNAPSHOT · * CURRENT",
            current_context=setup.current_context,
        ),
        height=min(8, max(3, len(setup.target_names))),
    )
    bindings = KeyBindings()
    status = {"value": ""}

    mode = HorizontalChoiceState(
        (
            HorizontalChoiceOption(
                "CONTEXT",
                "CONTEXT",
                "Retain one direct or recursive Context scope by value.",
            ),
            HorizontalChoiceOption(
                "MEMORY",
                "MEMORY",
                "Retain one exact direct Source Memory version by value.",
            ),
        ),
        selected_uid="CONTEXT",
    )
    mode_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            mode,
            title="SNAPSHOT UNIT",
            focused=get_app().layout.has_focus(mode_control),
            show_description=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    mode_frame = build_focused_frame(
        Window(mode_control, wrap_lines=True),
        title="SNAPSHOT UNIT",
        is_focused=lambda: get_app().layout.has_focus(mode_control),
        height=Dimension.exact(4),
    )
    scope = HorizontalChoiceState(
        (
            HorizontalChoiceOption(
                "DIRECT",
                "DIRECT · -d",
                "Capture only the selected Context.",
            ),
            HorizontalChoiceOption(
                "RECURSIVE",
                "RECURSIVE · -r",
                "Also include descendants and local embedded Contexts.",
            ),
        ),
        selected_uid="DIRECT",
    )
    scope_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            scope,
            title="CONTEXT SCOPE",
            focused=get_app().layout.has_focus(scope_control),
            show_description=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    scope_frame = build_focused_frame(
        Window(scope_control, wrap_lines=True),
        title="CONTEXT SCOPE",
        is_focused=lambda: get_app().layout.has_focus(scope_control),
        height=Dimension.exact(4),
    )

    def selected_request() -> ReferenceRequest | ContextReferenceRequest:
        if mode.selected_uid == "CONTEXT":
            recursive = scope.selected_uid == "RECURSIVE"
            return ContextReferenceRequest(
                source_locator=context_source.selection.selected_name,
                into_locator=target.selection.selected_name,
                include_descendants=recursive,
                follow_embeds=recursive,
            )
        memory = memory_source.selected
        if memory is None:
            raise ValueError("Select one direct Source Memory first.")
        return ReferenceRequest(
            memory_selector=memory.memory_uid,
            source_locator=memory.context_name,
            into_locator=target.selection.selected_name,
        )

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        try:
            request = selected_request()
            exact = (
                context_reference_exact_command_review(request)
                if isinstance(request, ContextReferenceRequest)
                else reference_exact_command_review(request)
            )
            review = render_exact_command_review(exact)
            action = "PRESS ENTER TO RETAIN THE REVIEWED SNAPSHOT"
        except ValueError as error:
            review = f"SOURCE REQUIRED · {display_escape_text(str(error))}"
            action = "SELECT THE SOURCE FIRST"
        return [
            ("", review + "\n\n"),
            ("[SetCursorPosition]", "") if focused else ("", ""),
            (focused_control_style(focused=focused), f"[ {action} ]"),
        ]

    todo_control = FormattedTextControl(render_todo, focusable=True, show_cursor=False)
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · EXACT COMMAND",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension(min=11, max=15),
    )
    header = Window(
        FormattedTextControl(
            lambda: (
                " MEM REFERENCE · IMMUTABLE SNAPSHOT → INTO\n"
                + (
                    " CHOOSE ONE SOURCE CONTEXT, SCOPE, AND TARGET"
                    if mode.selected_uid == "CONTEXT"
                    else " CHOOSE ONE EXACT SOURCE MEMORY AND TARGET"
                )
            )
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def footer_text() -> str:
        if status["value"]:
            return " " + display_escape_text(status["value"])
        if get_app().layout.has_focus(mode_control):
            return " ←/→ choose Context or Memory · Tab continue · Esc cancel"
        if get_app().layout.has_focus(memory_source.control):
            return (
                " ↑/↓ move · ←/→ expand · Enter choose direct Memory · "
                "Tab target · Esc cancel"
            )
        if get_app().layout.has_focus(context_source.control):
            return " ↑/↓ move · ←/→ tree · Enter choose Source · Tab scope"
        if get_app().layout.has_focus(scope_control):
            return " ←/→ choose direct or recursive · Tab target · Esc cancel"
        if get_app().layout.has_focus(target.control):
            return (
                " ↑/↓ move · ←/→ tree · Enter choose Target · Tab review · Esc cancel"
            )
        return " Enter retain exact snapshot · ↑ target · Tab source · Esc cancel"

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(mode_frame),
        TuiRegion(
            ConditionalContainer(
                content=context_source.frame,
                filter=Condition(lambda: mode.selected_uid == "CONTEXT"),
            )
        ),
        TuiRegion(
            ConditionalContainer(
                content=scope_frame,
                filter=Condition(lambda: mode.selected_uid == "CONTEXT"),
            )
        ),
        TuiRegion(
            ConditionalContainer(
                content=memory_source.frame,
                filter=Condition(lambda: mode.selected_uid == "MEMORY"),
            )
        ),
        TuiRegion(target.frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[
        FrozenReferencePlan | FrozenContextReferencePlan | None
    ] = Application(
        layout=Layout(root, focused_element=mode_control),
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
            memory_source.choose_cursor()
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def choose_context_source(_event) -> SurfaceActionResult:
        try:
            context_source.choose_cursor()
        except ValueError as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def choose_target(_event) -> SurfaceActionResult:
        try:
            target.choose_cursor()
        except ValueError as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def finish(event) -> SurfaceActionResult:
        try:
            request = selected_request()
            if isinstance(request, ContextReferenceRequest):
                expected = context_reference_exact_command_review(request)
                frozen = prepare_context(request)
                canonical_request = ContextReferenceRequest(
                    frozen.source_name,
                    frozen.into_name,
                    include_descendants=frozen.request.include_descendants,
                    follow_embeds=frozen.request.follow_embeds,
                )
                actual = context_reference_exact_command_review(canonical_request)
            else:
                expected = reference_exact_command_review(request)
                frozen = prepare(request)
                canonical_request = ReferenceRequest(
                    frozen.memory_uid,
                    frozen.source_name,
                    frozen.into_name,
                )
                actual = reference_exact_command_review(canonical_request)
            if actual != expected:
                raise RuntimeError(
                    "The exact Reference command changed while it was reviewed."
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

    def move_target(_event, delta: int):
        before = target.tree.selected_name
        target.move(delta)
        return "MOVED" if target.tree.selected_name != before else "BOUNDARY"

    def move_context_source(_event, delta: int):
        before = context_source.tree.selected_name
        context_source.move(delta)
        return (
            "MOVED"
            if context_source.tree.selected_name != before
            else "BOUNDARY"
        )

    surfaces = SurfaceFocusController(
        lambda: (
            FocusSurface(
                "MODE",
                mode_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
            ),
            *(
                (
                    FocusSurface(
                        "SOURCE_CONTEXT",
                        context_source.control,
                        move_vertical=move_context_source,
                        activate=choose_context_source,
                    ),
                    FocusSurface(
                        "SCOPE",
                        scope_control,
                        move_vertical=lambda _event, _delta: "BOUNDARY",
                    ),
                )
                if mode.selected_uid == "CONTEXT"
                else (
                    FocusSurface(
                        "SOURCE_MEMORY",
                        memory_source.control,
                        move_vertical=lambda _event, delta: (
                            "MOVED" if memory_source.move(delta) else "BOUNDARY"
                        ),
                        activate=choose_source,
                    ),
                )
            ),
            FocusSurface(
                "TARGET",
                target.control,
                move_vertical=move_target,
                activate=choose_target,
            ),
            FocusSurface(
                "TO_DO",
                todo_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=finish,
            ),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    memory_source_focus = Condition(
        lambda: get_app().layout.has_focus(memory_source.control)
    )
    context_source_focus = Condition(
        lambda: get_app().layout.has_focus(context_source.control)
    )
    target_focus = Condition(lambda: get_app().layout.has_focus(target.control))
    mode_focus = Condition(lambda: get_app().layout.has_focus(mode_control))
    scope_focus = Condition(lambda: get_app().layout.has_focus(scope_control))

    @bindings.add("left", filter=memory_source_focus, eager=True)
    def _collapse_source(event) -> None:
        memory_source.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=memory_source_focus, eager=True)
    def _expand_source(event) -> None:
        memory_source.expand()
        event.app.invalidate()

    @bindings.add("left", filter=context_source_focus, eager=True)
    def _collapse_context_source(event) -> None:
        context_source.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=context_source_focus, eager=True)
    def _expand_context_source(event) -> None:
        context_source.expand()
        event.app.invalidate()

    @bindings.add("left", filter=target_focus, eager=True)
    def _collapse_target(event) -> None:
        target.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=target_focus, eager=True)
    def _expand_target(event) -> None:
        target.expand()
        event.app.invalidate()

    @bindings.add("left", filter=mode_focus, eager=True)
    def _previous_mode(event) -> None:
        mode.move(-1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=mode_focus, eager=True)
    def _next_mode(event) -> None:
        mode.move(1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("left", filter=scope_focus, eager=True)
    def _direct_scope(event) -> None:
        scope.move(-1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=scope_focus, eager=True)
    def _recursive_scope(event) -> None:
        scope.move(1)
        status["value"] = ""
        event.app.invalidate()

    read_only_focus = Condition(lambda: surfaces.active(get_app()) is not None)

    bind_tui_interrupt(
        bindings,
        lambda event: event.app.exit(result=None),
    )

    @bindings.add("escape", filter=read_only_focus, eager=True)
    @bindings.add("backspace", filter=read_only_focus, eager=True)
    def _cancel(event) -> None:
        dispatch_tui_back(event, close=lambda current: current.app.exit(result=None))

    return app.run()


__all__ = [
    "context_reference_exact_command_review",
    "reference_exact_command_review",
    "run_reference_tui",
]
