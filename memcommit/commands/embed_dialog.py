"""Interactive Child, Into, and direct-item gap setup for ``mem embed``."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

import memcommit.ops as ops
from memcommit.commands.direct_item_placement import (
    DirectItemGap,
    DirectItemPlacementTreeProjection,
    direct_item_placement_rows,
)
from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    render_exact_command_review,
)
from memcommit.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
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
from memcommit.interfaces.tui.core.keybindings import dispatch_tui_back
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class EmbedSetupReceipt:
    """One reviewed canonical relationship and frozen insertion gap."""

    child_name: str
    into_name: str
    gap: DirectItemGap
    child_uid: str
    child_digest: str
    into_uid: str
    into_digest: str
    review: ExactCommandReview


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


def choose_embed_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> EmbedSetupReceipt | None:
    """Choose two local Contexts and one exact gap in the target's item order."""

    names = tuple(store.list_context_names())
    if len(names) < 2:
        raise ValueError("Interactive Embed requires at least two local Contexts.")
    if len(set(names)) != len(names):
        raise ValueError("Interactive Embed requires a distinct local catalog.")
    if require_tty:
        require_interactive_terminal(
            "Interactive Embed setup",
            snapshot_hint="Pass CHILD --into CONTEXT outside a terminal.",
        )

    current = store.current_context_name()
    initial_into = current if current in names else names[0]
    initial_child = next(name for name in names if name != initial_into)
    selector_height = min(6, max(3, len(names)))
    child_selector = ContextSelectorControl(
        ContextSelectorView(
            names=names,
            selected=(initial_child,),
            label="CHILD · EMBED THIS CONTEXT",
            current_context=current,
        ),
        height=selector_height,
    )
    target_snapshot = {"value": store.load_direct(initial_into)}
    placement = DirectItemPlacementTreeProjection.create(
        initial_into,
        direct_item_placement_rows(target_snapshot["value"]),
    )
    into_selector = ContextSelectorControl(
        ContextSelectorView(
            names=names,
            selected=(initial_into,),
            label="INTO + POSITION · CHANGE THIS CONTEXT · * CURRENT",
            current_context=current,
        ),
        height=selector_height,
        row_projector=placement.project,
    )
    status = {"value": ""}
    bindings = KeyBindings()

    def selected_child_name() -> str:
        return child_selector.selection.selected_name

    def selected_into_name() -> str:
        return into_selector.selection.selected_name

    def selected_review() -> ExactCommandReview:
        return embed_exact_command_review(
            selected_child_name(),
            selected_into_name(),
            placement.state.selected_gap,
            item_count=len(placement.state.rows),
        )

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        fragments: list[tuple[str, str]] = [
            ("", render_exact_command_review(selected_review())),
            ("", "\n\n"),
            ("[SetCursorPosition]", "") if focused else ("", ""),
            (
                focused_control_style(focused=focused),
                "[ PRESS ENTER TO EMBED AT THE REVIEWED GAP ]",
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
            " MEM EMBED · CHILD → INTO\n"
            " CHOOSE TWO LOCAL CONTEXTS AND ONE DIRECT-ITEM INSERTION GAP"
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

    def choose_into(_event) -> SurfaceActionResult:
        try:
            changed = into_selector.choose_cursor()
            if changed:
                name = selected_into_name()
                snapshot = store.load_direct(name)
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
            child = store.load_direct(selected_child_name())
            target = target_snapshot["value"]
            if target.name != selected_into_name():
                raise RuntimeError("The visible Embed target is no longer selected.")
            gap = placement.state.selected_gap
            ops.validate_embed(child, target, position=gap.position)
            review = selected_review()
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(
            result=EmbedSetupReceipt(
                child_name=child.name,
                into_name=target.name,
                gap=gap,
                child_uid=child.uid,
                child_digest=context_record_digest(child),
                into_uid=target.uid,
                into_digest=context_record_digest(target),
                review=review,
            )
        )
        return "HANDLED"

    surfaces = SurfaceFocusController(
        (
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
            ),
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
    )
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
        TuiRegion(child_selector.frame),
        TuiRegion(into_position_frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[EmbedSetupReceipt | None] = Application(
        layout=Layout(root, focused_element=child_selector.control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    return app.run()
