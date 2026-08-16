"""Interactive Child, Into, and direct-item gap setup for ``mem embed``."""

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
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.interfaces.tui.components.direct_item_placement import (
    DirectItemGap,
    DirectItemPlacementTreeProjection,
    direct_item_placement_rows,
)
from memcommit.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
    render_exact_command_review,
)
from memcommit.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorRowProjection,
    ContextSelectorView,
)
from memcommit.context_targeting.tui.memory_selection import (
    DirectMemorySelectionState,
)
from memcommit.context_targeting.tui.picker import (
    ContextMemoryPreviewController,
    ContextMemoryRow,
)
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import display_escape_text
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
from memcommit.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.interfaces.tui.core.keybindings import dispatch_tui_back
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.context import Context
from memcommit.embed_application import (
    EmbedPlacement,
    FrozenEmbedPlan,
    FrozenMemoryEmbedPlan,
)
from memcommit.interfaces.tui.operations.embed.model import EmbedTuiSetup


def _placement_argv(gap: DirectItemGap) -> tuple[str, ...]:
    """Represent every nonempty selected gap with one stable adjacent UID."""

    if gap.next_uid is not None:
        return ("--before", gap.next_uid)
    if gap.previous_uid is not None:
        return ("--after", gap.previous_uid)
    return ()


def _gap_effect(gap: DirectItemGap, item_count: int) -> str:
    if gap.previous_uid is not None and gap.next_uid is not None:
        location = (
            f"between [{gap.previous_uid[:8]}] and [{gap.next_uid[:8]}]"
        )
    elif gap.next_uid is not None:
        location = f"before [{gap.next_uid[:8]}] at the start"
    elif gap.previous_uid is not None:
        location = f"after [{gap.previous_uid[:8]}] at the end"
    else:
        location = "as the only direct item"
    return (
        f"Insert at gap {gap.position + 1}/{item_count + 1}, {location}."
    )


def embed_exact_command_review(
    child_name: str,
    into_name: str,
    gap: DirectItemGap,
    *,
    item_count: int,
) -> ExactCommandReview:
    """Build the exact command and complete one-Context mutation boundary."""

    return ExactCommandReview(
        argv=(
            "mem",
            "embed",
            child_name,
            "--into",
            into_name,
            *_placement_argv(gap),
        ),
        effects=(
            f"Only Context '{into_name}' is changed.",
            (
                f"Context '{child_name}' keeps its identity and ownership; "
                "the target stores a live Context reference."
            ),
            _gap_effect(gap, item_count),
        ),
    )


def memory_embed_exact_command_review(
    source_name: str,
    memory_uid: str,
    into_name: str,
    gap: DirectItemGap,
    *,
    item_count: int,
) -> ExactCommandReview:
    """Build the exact live-Memory command and its mutation boundary."""

    return ExactCommandReview(
        argv=(
            "mem",
            "embed",
            memory_uid,
            "--from",
            source_name,
            "--into",
            into_name,
            *_placement_argv(gap),
        ),
        effects=(
            f"Only Context '{into_name}' is changed.",
            (
                f"Memory [{memory_uid[:8]}] remains owned by '{source_name}'; "
                "the target stores a live Memory link."
            ),
            _gap_effect(gap, item_count),
        ),
    )


def run_embed_tui(
    setup: EmbedTuiSetup,
    *,
    inspect_context: Callable[[str], Context],
    freeze_exact_gap: Callable[
        [str, str, EmbedPlacement],
        FrozenEmbedPlan,
    ],
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]],
    freeze_memory_exact_gap: Callable[
        [str, str, str, EmbedPlacement],
        FrozenMemoryEmbedPlan,
    ],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenEmbedPlan | FrozenMemoryEmbedPlan | None:
    """Choose one live Context or Memory link and one target insertion gap."""

    if not isinstance(setup, EmbedTuiSetup):
        raise TypeError("Embed TUI requires an EmbedTuiSetup.")
    child_names = setup.child_names
    into_names = setup.into_names
    memory_source_names = setup.memory_source_names
    if require_tty:
        require_interactive_terminal(
            "Interactive Embed setup",
            snapshot_hint=(
                "Pass CHILD --into CONTEXT, or MEMORY --from SOURCE --into "
                "CONTEXT, outside a terminal."
            ),
        )

    current = setup.current_context
    initial_into = current if current in into_names else into_names[0]
    try:
        initial_child = next(
            name
            for name in child_names
            if name != initial_into and name in setup.child_selectable_names
        )
    except StopIteration as error:
        raise ValueError(
            "Interactive Embed requires an authorized Child distinct from its target."
        ) from error
    selector_height = min(6, max(3, len(child_names)))
    child_selector = ContextSelectorControl(
        ContextSelectorView(
            names=child_names,
            selected=(initial_child,),
            label="CHILD · EMBED THIS CONTEXT",
            current_context=current,
            selectable_names=setup.child_selectable_names,
            annotations=setup.child_annotations,
        ),
        height=selector_height,
    )
    initial_memory_source = next(
        (name for name in memory_source_names if name != initial_into),
        memory_source_names[0],
    )
    memory_source_selector = ContextSelectorControl(
        ContextSelectorView(
            names=memory_source_names,
            selected=(initial_memory_source,),
            label="SOURCE MEMORY · DIRECTLY OWNED",
            current_context=current,
        ),
        height=min(6, max(3, len(memory_source_names))),
    )
    memory_preview = ContextMemoryPreviewController(
        memory_source_selector.tree,
        memory_loader,
    )
    memory_selection = DirectMemorySelectionState()

    def project_memory_source(row, focused) -> ContextSelectorRowProjection:
        width = max(1, get_app().output.get_size().columns - 8)
        memory_focused = (
            memory_preview.memory_focused
            and memory_preview.memory_anchor is not None
            and memory_preview.memory_anchor[0] == row.name
        )
        return ContextSelectorRowProjection(
            branch=memory_preview.branch_for(row),
            nested_fragments=memory_preview.render_nested(
                row,
                wrap_width=width,
                selectable_memories=True,
                selected_memory=memory_selection.selected,
            ),
            show_context_cursor=not (focused and memory_focused),
        )

    memory_source_selector.row_projector = project_memory_source
    memory_preview.toggle_selected_memories()
    mode = HorizontalChoiceState(
        (
            HorizontalChoiceOption(
                "CONTEXT",
                "CONTEXT",
                "Keep one Child Context live inside the Target.",
            ),
            HorizontalChoiceOption(
                "MEMORY",
                "MEMORY",
                "Keep one directly owned Source Memory live inside the Target.",
            ),
        ),
        selected_uid="CONTEXT",
    )
    mode_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            mode,
            title="LINK TYPE",
            focused=get_app().layout.has_focus(mode_control),
            show_description=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    mode_frame = build_focused_frame(
        Window(mode_control, wrap_lines=True),
        title="LINK TYPE",
        is_focused=lambda: get_app().layout.has_focus(mode_control),
        height=Dimension.exact(4),
    )
    target_snapshot = {"value": inspect_context(initial_into)}
    placement = DirectItemPlacementTreeProjection.create(
        initial_into,
        direct_item_placement_rows(target_snapshot["value"]),
    )
    into_selector = ContextSelectorControl(
        ContextSelectorView(
            names=into_names,
            selected=(initial_into,),
            label="INTO + POSITION · CHANGE THIS CONTEXT · * CURRENT",
            current_context=current,
        ),
        height=min(6, max(3, len(into_names))),
        row_projector=placement.project,
    )
    status = {"value": ""}
    bindings = KeyBindings()

    def selected_child_name() -> str:
        return child_selector.selection.selected_name

    def selected_into_name() -> str:
        return into_selector.selection.selected_name

    def selected_memory_target():
        target = memory_selection.selected
        if target is None:
            raise ValueError("Select one directly owned Source Memory first.")
        return target

    def selected_review() -> ExactCommandReview:
        if mode.selected_uid == "MEMORY":
            target = selected_memory_target()
            return memory_embed_exact_command_review(
                target.context_name,
                target.memory_uid,
                selected_into_name(),
                placement.state.selected_gap,
                item_count=len(placement.state.rows),
            )
        return embed_exact_command_review(
            selected_child_name(),
            selected_into_name(),
            placement.state.selected_gap,
            item_count=len(placement.state.rows),
        )

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        try:
            review_text = render_exact_command_review(selected_review())
            action = "[ PRESS ENTER TO EMBED AT THE REVIEWED GAP ]"
        except ValueError as error:
            review_text = f"INCOMPLETE · {display_escape_text(str(error))}"
            action = "[ SELECT A DIRECT SOURCE MEMORY FIRST ]"
        fragments: list[tuple[str, str]] = [
            ("", review_text),
            ("", "\n\n"),
            ("[SetCursorPosition]", "") if focused else ("", ""),
            (
                focused_control_style(focused=focused),
                action,
            ),
        ]
        return fragments

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · EXACT COMMAND",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension(min=10, max=14),
    )
    into_position_frame = build_focused_frame(
        Window(
            into_selector.control,
            wrap_lines=False,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        ),
        title="INTO + POSITION · CHANGE THIS CONTEXT",
        is_focused=lambda: get_app().layout.has_focus(into_selector.control),
        height=Dimension(min=14, weight=1),
    )
    header = Window(
        FormattedTextControl(
            lambda: (
                " MEM EMBED · LIVE LINK → INTO\n"
                + (
                    " CHOOSE ONE CHILD CONTEXT AND ONE DIRECT-ITEM INSERTION GAP"
                    if mode.selected_uid == "CONTEXT"
                    else " CHOOSE ONE DIRECT SOURCE MEMORY AND ONE INSERTION GAP"
                )
            )
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if status["value"]:
            return f" {display_escape_text(status['value'])}"
        if (
            get_app().layout.has_focus(into_selector.control)
            and placement.editing
        ):
            return (
                " ↑/↓ move one position line · Enter/Space stage · "
                "Tab review · Esc back to Context"
            )
        if get_app().layout.has_focus(into_selector.control):
            return (
                " ↑/↓ move in Context tree · "
                "Enter/Space choose target · Tab edit position · Esc cancel"
            )
        if get_app().layout.has_focus(todo_control):
            return " Enter apply exact command · ↑ position · Esc cancel"
        if get_app().layout.has_focus(mode_control):
            return " ←/→ choose Memory or Context · Tab continue · Esc cancel"
        if get_app().layout.has_focus(memory_source_selector.control):
            return (
                " ↑/↓ move · ←/→ expand · Enter choose direct Memory · "
                "Tab target · Esc cancel"
            )
        return (
            " ↑/↓ move · ←/→ tree · Enter/Space choose Context · "
            "Tab next frame · Esc cancel"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    def move_selector(
        selector: ContextSelectorControl,
        delta: int,
    ) -> SurfaceMoveResult:
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def enter_selector(selector: ContextSelectorControl, delta: int) -> None:
        rows = selector.tree.visible_rows()
        selector.tree.selected_name = rows[0 if delta > 0 else -1].name

    def choose_child(_event) -> SurfaceActionResult:
        try:
            child_selector.choose_cursor()
        except ValueError as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def move_memory_source(_event, delta: int) -> SurfaceMoveResult:
        return "MOVED" if memory_preview.move(delta) else "BOUNDARY"

    def choose_memory_source(_event) -> SurfaceActionResult:
        try:
            if not memory_preview.memory_focused:
                name = memory_source_selector.tree.selected_name
                memory_source_selector.selection.choose(name)
                memory_selection.clear_unless_context(name)
                memory_preview.toggle_selected_memories()
            else:
                target = memory_preview.focused_target()
                if target is None:
                    raise ValueError(
                        "Only a directly owned ordinary Memory can be embedded."
                    )
                memory_selection.choose(target)
                memory_source_selector.selection.choose(target.context_name)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def choose_into(_event) -> SurfaceActionResult:
        try:
            changed = into_selector.choose_cursor()
            if changed:
                name = selected_into_name()
                snapshot = inspect_context(name)
                target_snapshot["value"] = snapshot
                placement.replace_context(
                    name,
                    direct_item_placement_rows(snapshot),
                )
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def begin_position() -> None:
        into_selector.tree.selected_name = selected_into_name()
        placement.begin()

    def move_into(_event, delta: int) -> SurfaceMoveResult:
        if placement.editing:
            if placement.state.move(delta):
                return "MOVED"
            if delta < 0:
                placement.end()
                into_selector.tree.selected_name = selected_into_name()
                return "CONSUMED"
            return "BOUNDARY"
        result = move_selector(into_selector, delta)
        if result == "BOUNDARY" and delta > 0:
            begin_position()
            return "CONSUMED"
        return result

    def choose_into_or_position(event) -> SurfaceActionResult:
        if not placement.editing:
            return choose_into(event)
        placement.state.choose_cursor()
        status["value"] = ""
        return "HANDLED"

    def enter_into(delta: int) -> None:
        if delta < 0:
            begin_position()
            placement.state.cursor_position = len(placement.state.rows)
            return
        placement.end()
        enter_selector(into_selector, delta)

    def finish(event) -> SurfaceActionResult:
        try:
            target = target_snapshot["value"]
            if target.name != selected_into_name():
                raise RuntimeError("The visible Embed target is no longer selected.")
            gap = placement.state.selected_gap
            requested_placement = EmbedPlacement(
                position=gap.position,
                previous_uid=gap.previous_uid,
                next_uid=gap.next_uid,
            )
            expected_review = selected_review()
            if mode.selected_uid == "MEMORY":
                memory_target = selected_memory_target()
                frozen = freeze_memory_exact_gap(
                    memory_target.context_name,
                    memory_target.memory_uid,
                    target.name,
                    requested_placement,
                )
                rebuilt_review = memory_embed_exact_command_review(
                    frozen.source_name,
                    frozen.memory_uid,
                    frozen.into_name,
                    DirectItemGap(
                        position=frozen.placement.position,
                        previous_uid=frozen.placement.previous_uid,
                        next_uid=frozen.placement.next_uid,
                    ),
                    item_count=frozen.item_count,
                )
            else:
                frozen = freeze_exact_gap(
                    selected_child_name(),
                    target.name,
                    requested_placement,
                )
                rebuilt_review = embed_exact_command_review(
                    frozen.child_name,
                    frozen.into_name,
                    DirectItemGap(
                        position=frozen.placement.position,
                        previous_uid=frozen.placement.previous_uid,
                        next_uid=frozen.placement.next_uid,
                    ),
                    item_count=frozen.item_count,
                )
            if rebuilt_review != expected_review:
                raise RuntimeError(
                    "The exact Embed command changed while it was reviewed."
                )
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(
            result=frozen
        )
        return "HANDLED"

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        source = (
            FocusSurface(
                "CHILD",
                child_selector.control,
                move_vertical=lambda _event, delta: move_selector(
                    child_selector, delta
                ),
                activate=choose_child,
                on_vertical_enter=lambda delta: enter_selector(
                    child_selector, delta
                ),
            )
            if mode.selected_uid == "CONTEXT"
            else FocusSurface(
                "SOURCE_MEMORY",
                memory_source_selector.control,
                move_vertical=move_memory_source,
                activate=choose_memory_source,
            )
        )
        return (
            FocusSurface(
                "LINK_TYPE",
                mode_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=lambda _event: "HANDLED",
            ),
            source,
            FocusSurface(
                "INTO_POSITION",
                into_selector.control,
                move_vertical=move_into,
                activate=choose_into_or_position,
                on_vertical_enter=enter_into,
            ),
            FocusSurface(
                "TO_DO",
                todo_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=finish,
            ),
        )

    surfaces = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surfaces, tab=False)

    @bindings.add("tab", eager=True)
    def _next_surface(event) -> None:
        if get_app().layout.has_focus(into_selector.control):
            if not placement.editing:
                begin_position()
            else:
                surfaces.focus_relative(event.app, 1, wrap=True)
        else:
            surfaces.focus_relative(event.app, 1, wrap=True)
            if get_app().layout.has_focus(into_selector.control):
                placement.end()
        event.app.invalidate()

    @bindings.add("s-tab", eager=True)
    def _previous_surface(event) -> None:
        if get_app().layout.has_focus(into_selector.control):
            if placement.editing:
                placement.end()
                into_selector.tree.selected_name = selected_into_name()
            else:
                surfaces.focus_relative(event.app, -1, wrap=True)
        else:
            surfaces.focus_relative(event.app, -1, wrap=True)
            if get_app().layout.has_focus(into_selector.control):
                begin_position()
        event.app.invalidate()

    mode_focus = Condition(lambda: get_app().layout.has_focus(mode_control))
    memory_source_focus = Condition(
        lambda: get_app().layout.has_focus(memory_source_selector.control)
    )
    selector_focus = Condition(
        lambda: get_app().layout.has_focus(child_selector.control)
        or (
            get_app().layout.has_focus(into_selector.control)
            and not placement.editing
        )
    )

    def focused_selector() -> ContextSelectorControl:
        return (
            child_selector
            if get_app().layout.has_focus(child_selector.control)
            else into_selector
        )

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

    @bindings.add("left", filter=memory_source_focus, eager=True)
    def _collapse_memory_source(event) -> None:
        memory_preview.collapse_selected()
        event.app.invalidate()

    @bindings.add("right", filter=memory_source_focus, eager=True)
    def _expand_memory_source(event) -> None:
        memory_preview.expand_selected()
        event.app.invalidate()

    @bindings.add("a", filter=memory_source_focus, eager=True)
    @bindings.add("A", filter=memory_source_focus, eager=True)
    def _toggle_all_memory_sources(event) -> None:
        memory_preview.toggle_expand_all()
        event.app.invalidate()

    @bindings.add("left", filter=selector_focus, eager=True)
    def _collapse(event) -> None:
        focused_selector().collapse()
        event.app.invalidate()

    @bindings.add("right", filter=selector_focus, eager=True)
    def _expand(event) -> None:
        focused_selector().expand()
        event.app.invalidate()

    @bindings.add("a", filter=selector_focus, eager=True)
    @bindings.add("A", filter=selector_focus, eager=True)
    def _toggle_expand_all(event) -> None:
        focused_selector().toggle_expand_all()
        event.app.invalidate()

    @bindings.add(" ", eager=True)
    def _activate_with_space(event) -> None:
        if surfaces.active_supports(event.app, "activate"):
            surfaces.activate(event)
            event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=None)

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _cancel(event) -> None:
        if (
            get_app().layout.has_focus(into_selector.control)
            and placement.editing
        ):
            placement.end()
            into_selector.tree.selected_name = selected_into_name()
            event.app.invalidate()
            return
        dispatch_tui_back(event, close=close)

    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(mode_frame),
        TuiRegion(
            ConditionalContainer(
                content=child_selector.frame,
                filter=Condition(lambda: mode.selected_uid == "CONTEXT"),
            )
        ),
        TuiRegion(
            ConditionalContainer(
                content=memory_source_selector.frame,
                filter=Condition(lambda: mode.selected_uid == "MEMORY"),
            )
        ),
        TuiRegion(into_position_frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[
        FrozenEmbedPlan | FrozenMemoryEmbedPlan | None
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
    return app.run()
