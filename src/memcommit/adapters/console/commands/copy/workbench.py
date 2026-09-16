"""Copy-owned interactive workbench reused by direct-Memory Move.

One command package owns the screen so sharing it does not introduce a third
command. Each setup adapter supplies its own catalogs and plan-freeze callback;
screen ownership does not give Move Copy's granted-Source authority.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.coordination.copy_and_move.model import (
    CopyAndMoveTuiSetup,
)
from memcommit.adapters.console.terminal.components.action import build_action_control
from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
)
from memcommit.adapters.console.terminal.components.direct_item_placement import (
    DirectItemPlacementTreeProjection,
    direct_item_placement_rows,
)
from memcommit.adapters.console.terminal.components.focus.controller import (
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
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.direct_memory_selector import (
    DirectMemorySelectorControl,
    DirectMemorySelectorView,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_tui_interrupt,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.memory_transfer.contracts import (
    MemoryTransferPlacement,
)
from memcommit.application.operations.copy.application import (
    validate_copy_request,
)
from memcommit.application.operations.copy.contracts import (
    CopyMemoriesRequest,
    FrozenCopyMemoriesPlan,
)
from memcommit.application.operations.move.application import (
    validate_move_request,
)
from memcommit.application.operations.move.contracts import (
    FrozenMoveMemoriesPlan,
    MoveMemoriesRequest,
)
from memcommit.core.context import Context


def run_copy_and_move_workbench(
    setup: CopyAndMoveTuiSetup,
    *,
    kind: str,
    inspect_into_context: Callable[[str], Context],
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]],
    freeze_plan: Callable[
        [CopyMemoriesRequest | MoveMemoriesRequest],
        FrozenCopyMemoriesPlan | FrozenMoveMemoriesPlan,
    ],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenCopyMemoriesPlan | FrozenMoveMemoriesPlan | None:
    """Choose multiple Sources and one Target gap, then freeze on Apply."""

    if not isinstance(setup, CopyAndMoveTuiSetup):
        raise TypeError("Copy/Move TUI requires a typed setup.")
    operation = kind.upper()
    if operation not in {"COPY", "MOVE"}:
        raise ValueError("Copy/Move kind must be COPY or MOVE.")
    if require_tty:
        require_interactive_terminal(
            f"Interactive {operation.title()} setup",
            snapshot_hint=(
                "Pass one or more MEMORY locators and --into TARGET outside a terminal."
            ),
        )

    source_names = setup.source_names
    into_names = setup.into_names
    current = setup.current_context
    initial_source = current if current in source_names else source_names[0]
    initial_into = current if current in into_names else into_names[0]
    source_selector = DirectMemorySelectorControl(
        DirectMemorySelectorView(
            names=source_names,
            selected_context=initial_source,
            label=f"SOURCE MEMORIES · {operation} THESE DIRECT ITEMS · * CURRENT",
            current_context=current,
            annotations=setup.source_annotations,
            mode="MULTIPLE",
        ),
        memory_loader=memory_loader,
        height=min(13, max(7, len(source_names) + 4)),
    )
    target_snapshot = {"value": inspect_into_context(initial_into)}
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
        height=min(7, max(3, len(into_names))),
        row_projector=placement.project,
    )
    link_policy = HorizontalChoiceState(
        (
            HorizontalChoiceOption(
                "RETARGET",
                "FOLLOW MOVE",
                "Live Embeds follow the moved Memory; snapshots stay unchanged.",
            ),
            HorizontalChoiceOption(
                "BREAK",
                "BREAK LINKS",
                "Live Embeds may become dangling; snapshots stay unchanged.",
            ),
        ),
        selected_uid="RETARGET",
    )
    status = {"value": ""}
    bindings = KeyBindings()

    def selected_into_name() -> str:
        return into_selector.selection.selected_name

    def selected_request() -> CopyMemoriesRequest | MoveMemoriesRequest:
        selected = source_selector.selected_many
        if not selected:
            raise ValueError("Select one or more direct Source Memories first.")
        gap = placement.state.selected_gap
        # Keep durable coordinates exact; shortening exists only for display.
        before = gap.next_uid
        after = gap.previous_uid if before is None else None
        locators = tuple(
            f"{target.context_name}:{target.memory_uid}" for target in selected
        )
        if operation == "COPY":
            return validate_copy_request(
                CopyMemoriesRequest(
                    memory_locators=locators,
                    into_locator=selected_into_name(),
                    before=before,
                    after=after,
                )
            )
        return validate_move_request(
            MoveMemoriesRequest(
                memory_locators=locators,
                into_locator=selected_into_name(),
                before=before,
                after=after,
                link_policy=link_policy.selected_uid,
            )
        )

    def describe_apply() -> str:
        count = len(source_selector.selected_many)
        if not count:
            return "Select one or more direct Source Memories."
        return (
            f"{operation.title()} {count} {'Memory' if count == 1 else 'Memories'} in selection order into {selected_into_name()} "
            f"at position {placement.state.selected_gap.position + 1}/{len(placement.state.rows) + 1}."
        )

    action_control = build_action_control("Apply", describe=describe_apply)
    action_line = Window(
        action_control, height=Dimension.exact(2), dont_extend_height=True
    )
    policy_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            link_policy,
            title="LIVE EMBEDS",
            focused=get_app().layout.has_focus(policy_control),
            inline_boxed=True,
            show_description=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    policy_line = Window(
        policy_control, height=Dimension.exact(2), dont_extend_height=True
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
            (
                f" MEM {operation} · DIRECT MEMORIES → INTO\n"
                " CHECK ONE OR MORE SOURCE MEMORIES, THEN CHOOSE ONE LOCAL TARGET GAP"
                + (
                    " · CHOOSE LIVE EMBED BEHAVIOR BELOW"
                    if operation == "MOVE"
                    else " · GRANTED SOURCES REQUIRE EXPLICIT PUBLIC OWNERS"
                )
            )
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if status["value"]:
            return f" {display_escape_text(status['value'])}"
        if get_app().layout.has_focus(action_control):
            return " Enter Apply · Esc cancel"
        if get_app().layout.has_focus(policy_control):
            return " ←/→ choose live Embed behavior · Tab Apply · Esc cancel"
        if get_app().layout.has_focus(into_selector.control) and placement.editing:
            return (
                " ↑/↓ move one position line · Enter/Space stage · "
                "Tab continue · Esc back to Context"
            )
        if get_app().layout.has_focus(into_selector.control):
            return (
                " ↑/↓ move in Context tree · Enter/Space choose target · "
                "Tab edit position · Esc cancel"
            )
        return (
            " ↑/↓ move · ←/→ expand · Enter/Space check Memory · "
            "Tab continue · Esc cancel"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    def move_source(_event, delta: int) -> SurfaceMoveResult:
        return "MOVED" if source_selector.move(delta) else "BOUNDARY"

    def choose_source(_event) -> SurfaceActionResult:
        try:
            source_selector.choose_cursor()
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def move_context(selector: ContextSelectorControl, delta: int) -> SurfaceMoveResult:
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def enter_context(selector: ContextSelectorControl, delta: int) -> None:
        rows = selector.tree.visible_rows()
        selector.tree.selected_name = rows[0 if delta > 0 else -1].name

    def choose_into(_event) -> SurfaceActionResult:
        try:
            changed = into_selector.choose_cursor()
            if changed:
                name = selected_into_name()
                snapshot = inspect_into_context(name)
                target_snapshot["value"] = snapshot
                placement.replace_context(name, direct_item_placement_rows(snapshot))
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
        result = move_context(into_selector, delta)
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
        enter_context(into_selector, delta)

    def finish(event) -> SurfaceActionResult:
        try:
            request = selected_request()
            target = target_snapshot["value"]
            if target.name != selected_into_name():
                raise RuntimeError(
                    f"The visible {operation.title()} target is no longer selected."
                )
            gap = placement.state.selected_gap
            expected_placement = MemoryTransferPlacement(
                position=gap.position,
                previous_uid=gap.previous_uid,
                next_uid=gap.next_uid,
            )
            frozen = freeze_plan(request)
            if frozen.placement != expected_placement:
                raise RuntimeError(
                    f"The exact {operation.title()} gap changed while it was reviewed."
                )
        except (
            FileNotFoundError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(result=frozen)
        return "HANDLED"

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        surfaces = [
            FocusSurface(
                "SOURCE_MEMORIES",
                source_selector.control,
                move_vertical=move_source,
                activate=choose_source,
            )
        ]
        surfaces.extend(
            (
                FocusSurface(
                    "INTO_POSITION",
                    into_selector.control,
                    move_vertical=move_into,
                    activate=choose_into_or_position,
                    on_vertical_enter=enter_into,
                ),
                *(
                    (
                        FocusSurface(
                            "LINK_POLICY",
                            policy_control,
                            move_vertical=lambda _event, _delta: "BOUNDARY",
                        ),
                    )
                    if operation == "MOVE"
                    else ()
                ),
                FocusSurface(
                    "APPLY",
                    action_control,
                    move_vertical=lambda _event, _delta: "BOUNDARY",
                    activate=finish,
                ),
            )
        )
        return tuple(surfaces)

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

    source_focus = Condition(
        lambda: get_app().layout.has_focus(source_selector.control)
    )
    target_focus = Condition(
        lambda: get_app().layout.has_focus(into_selector.control)
        and not placement.editing
    )
    action_focus = Condition(lambda: get_app().layout.has_focus(action_control))
    policy_focus = Condition(lambda: get_app().layout.has_focus(policy_control))

    @bindings.add("left", filter=policy_focus, eager=True)
    def _policy_left(event) -> None:
        link_policy.move(-1)
        event.app.invalidate()

    @bindings.add("right", filter=policy_focus, eager=True)
    def _policy_right(event) -> None:
        link_policy.move(1)
        event.app.invalidate()

    @bindings.add("left", filter=source_focus, eager=True)
    def _collapse_source(event) -> None:
        source_selector.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=source_focus, eager=True)
    def _expand_source(event) -> None:
        source_selector.expand()
        event.app.invalidate()

    @bindings.add("a", filter=source_focus, eager=True)
    @bindings.add("A", filter=source_focus, eager=True)
    def _toggle_all_sources(event) -> None:
        source_selector.toggle_expand_all()
        event.app.invalidate()

    @bindings.add("left", filter=target_focus, eager=True)
    def _collapse_target(event) -> None:
        into_selector.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=target_focus, eager=True)
    def _expand_target(event) -> None:
        into_selector.expand()
        event.app.invalidate()

    @bindings.add("a", filter=target_focus, eager=True)
    @bindings.add("A", filter=target_focus, eager=True)
    def _toggle_all_targets(event) -> None:
        into_selector.toggle_expand_all()
        event.app.invalidate()

    @bindings.add(" ", filter=~action_focus, eager=True)
    def _activate_with_space(event) -> None:
        if surfaces.active_supports(event.app, "activate"):
            surfaces.activate(event)
            event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=None)

    bind_tui_interrupt(bindings, close)

    @bindings.add("escape", eager=True)
    def _cancel(event) -> None:
        if get_app().layout.has_focus(into_selector.control) and placement.editing:
            placement.end()
            into_selector.tree.selected_name = selected_into_name()
            event.app.invalidate()
            return
        dispatch_tui_back(event, close=close)

    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        if get_app().layout.has_focus(into_selector.control) and placement.editing:
            placement.end()
            into_selector.tree.selected_name = selected_into_name()
            event.app.invalidate()
            return
        dispatch_tui_back(event, close=close)

    regions = [TuiRegion(header), TuiRegion(source_selector.frame)]
    regions.extend(
        (
            TuiRegion(into_position_frame),
            *([TuiRegion(policy_line)] if operation == "MOVE" else []),
            TuiRegion(action_line),
            TuiRegion(footer),
        )
    )
    root = build_tui_frame(*regions)
    app: Application[FrozenCopyMemoriesPlan | FrozenMoveMemoriesPlan | None] = (
        Application(
            layout=Layout(root, focused_element=source_selector.control),
            key_bindings=bindings,
            full_screen=True,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            mouse_support=False,
            style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        )
    )
    return app.run()


__all__ = ["run_copy_and_move_workbench"]
