"""Interactive Child, Into, and direct-item gap workbench for ``mem embed``."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import memcommit.application.capabilities.ops as ops
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

from memcommit.adapters.console.terminal.components.direct_item_placement import (
    DirectItemGap,
    DirectItemPlacementTreeProjection,
    direct_item_placement_rows,
)
from memcommit.adapters.console.terminal.components.exact_command_review import (
    EditableExactCommandControl,
    ExactCommandDraft,
    ExactCommandForm,
    ExactCommandFormField,
    CommandReview,
    resolve_displayed_command_value,
    shortest_unique_identifier_prefix,
)
from memcommit.core.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.core.context_targeting.tui.direct_memory_selector import (
    DirectMemorySelectorControl,
    DirectMemorySelectorView,
)
from memcommit.adapters.console.terminal.components.context_picker import ContextMemoryRow
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.adapters.console.terminal.core.capabilities import require_interactive_terminal
from memcommit.adapters.console.terminal.core.text import display_escape_text
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
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_tui_interrupt,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.core.context import Context
from memcommit.application.operations.embed.application import (
    EmbedPlacement,
    EmbedRequest,
    FrozenEmbedPlan,
    FrozenMemoryEmbedPlan,
    MemoryEmbedRequest,
    validate_embed_request,
    validate_memory_embed_request,
)
from memcommit.adapters.console.commands.embed.workbench.model import EmbedTuiSetup


EMBED_COMMAND_FORM = ExactCommandForm(
    command=("mem", "embed"),
    usage=(
        "mem embed [ITEM] [--from SOURCE] --into TARGET [--before ITEM | --after ITEM]"
    ),
    fields=(
        ExactCommandFormField(
            "ITEM",
            "Child Context, or a Source Memory UID/prefix when --from is present",
        ),
        ExactCommandFormField(
            "--from SOURCE",
            (
                "select a Source Context when ITEM is omitted, or the directly "
                "owning Context for a Memory ITEM"
            ),
        ),
        ExactCommandFormField(
            "--into TARGET",
            "choose the one local Context whose direct order may change",
        ),
        ExactCommandFormField(
            "--before ITEM | --after ITEM",
            "choose one adjacent direct-item gap; omit to append",
        ),
    ),
)


def parse_embed_command_argv(
    argv: Sequence[str],
) -> EmbedRequest | MemoryEmbedRequest:
    """Parse the editable Embed subset without invoking a nested CLI."""

    values = tuple(argv)
    if values[:2] != ("mem", "embed"):
        raise ValueError("Editable Embed commands must start with 'mem embed'.")
    operands: list[str] = []
    options: dict[str, str] = {}
    index = 2
    known = {"--from", "--into", "--to", "--before", "--after"}
    while index < len(values):
        value = values[index]
        if value.startswith("--"):
            if value not in known:
                raise ValueError(f"Unknown Embed flag '{value}'.")
            if value in options:
                raise ValueError(f"Embed flag '{value}' may be supplied only once.")
            if index + 1 >= len(values) or values[index + 1].startswith("--"):
                raise ValueError(f"Embed flag '{value}' requires one value.")
            options[value] = values[index + 1]
            index += 2
            continue
        operands.append(value)
        index += 1
    if len(operands) > 1 or (not operands and "--from" not in options):
        raise ValueError(
            "Editable Embed commands require one ITEM operand or --from SOURCE."
        )
    if "--into" in options and "--to" in options:
        raise ValueError("Use only one of --into or --to.")
    into_locator = options.get("--into") or options.get("--to")
    if into_locator is None:
        raise ValueError(
            "Editable Embed commands require --into TARGET "
            "(or compatibility --to TARGET)."
        )
    if "--before" in options and "--after" in options:
        raise ValueError("Pass only one of --before or --after.")
    if operands and "--from" in options:
        locator = parse_direct_memory_locator(
            operands[0],
            explicit_context=options["--from"],
        )
        return validate_memory_embed_request(
            MemoryEmbedRequest(
                memory_selector=locator.memory_selector,
                source_locator=locator.context_locator or options["--from"],
                into_locator=into_locator,
                before=options.get("--before"),
                after=options.get("--after"),
            )
        )
    if operands and ":" in operands[0]:
        locator = parse_direct_memory_locator(operands[0])
        assert locator.context_locator is not None
        return validate_memory_embed_request(
            MemoryEmbedRequest(
                memory_selector=locator.memory_selector,
                source_locator=locator.context_locator,
                into_locator=into_locator,
                before=options.get("--before"),
                after=options.get("--after"),
            )
        )
    child_locator = operands[0] if operands else options["--from"]
    return validate_embed_request(
        EmbedRequest(
            child_locator=child_locator,
            into_locator=into_locator,
            before=options.get("--before"),
            after=options.get("--after"),
        )
    )


def _placement_argv(
    gap: DirectItemGap,
    *,
    selector: str | None = None,
) -> tuple[str, ...]:
    """Represent every nonempty selected gap with one stable adjacent UID."""

    if gap.next_uid is not None:
        return ("--before", selector or gap.next_uid)
    if gap.previous_uid is not None:
        return ("--after", selector or gap.previous_uid)
    return ()


def _gap_effect(gap: DirectItemGap, item_count: int) -> str:
    if gap.previous_uid is not None and gap.next_uid is not None:
        location = f"between [{gap.previous_uid[:8]}] and [{gap.next_uid[:8]}]"
    elif gap.next_uid is not None:
        location = f"before [{gap.next_uid[:8]}] at the start"
    elif gap.previous_uid is not None:
        location = f"after [{gap.previous_uid[:8]}] at the end"
    else:
        location = "as the only direct item"
    return f"Insert at gap {gap.position + 1}/{item_count + 1}, {location}."


def embed_exact_command_review(
    child_name: str,
    into_name: str,
    gap: DirectItemGap,
    *,
    item_count: int,
    placement_selector: str | None = None,
) -> CommandReview:
    """Build the exact command and complete one-Context mutation boundary."""

    return CommandReview(
        argv=(
            "mem",
            "embed",
            child_name,
            "--into",
            into_name,
            *_placement_argv(gap, selector=placement_selector),
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
    memory_selector: str | None = None,
    placement_selector: str | None = None,
    qualified_locator: bool = False,
) -> CommandReview:
    """Build the exact live-Memory command and its mutation boundary."""

    selector = memory_selector or memory_uid
    source_argv = (
        (f"{source_name}:{selector}",)
        if qualified_locator
        else (selector, "--from", source_name)
    )
    return CommandReview(
        argv=(
            "mem",
            "embed",
            *source_argv,
            "--into",
            into_name,
            *_placement_argv(gap, selector=placement_selector),
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
    # Source selection is process-local review state, not execution authority.
    # Start beside the current Target so its Memories are immediately visible;
    # the exact action boundary remains responsible for rejecting a self-link.
    initial_memory_source = (
        initial_into if initial_into in memory_source_names else memory_source_names[0]
    )
    memory_source_selector = DirectMemorySelectorControl(
        DirectMemorySelectorView(
            names=memory_source_names,
            selected_context=initial_memory_source,
            label="SOURCE MEMORY · DIRECT ITEM · LIVE LINK",
            current_context=current,
            selectable_names=setup.memory_source_selectable_names,
            annotations=setup.memory_source_annotations,
        ),
        memory_loader=memory_loader,
        height=min(6, max(3, len(memory_source_names))),
    )
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
                "Keep one direct Source Memory live inside the Target.",
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
        target = memory_source_selector.selected
        if target is None:
            raise ValueError("Select one direct Source Memory first.")
        return target

    def command_gap_selector(gap: DirectItemGap) -> str | None:
        anchor = gap.next_uid or gap.previous_uid
        if anchor is None:
            return None
        return shortest_unique_identifier_prefix(
            anchor,
            tuple(row.uid for row in placement.state.rows),
            minimum=7,
        )

    def command_memory_selector(context_name: str, memory_uid: str) -> str:
        rows = memory_source_selector.preview.memory_cache.get(context_name, ())
        candidates = tuple(row.selector for row in rows if row.selector is not None)
        return shortest_unique_identifier_prefix(
            memory_uid,
            candidates,
            minimum=7,
        )

    def selected_review() -> CommandReview:
        gap = placement.state.selected_gap
        gap_selector = command_gap_selector(gap)
        if mode.selected_uid == "MEMORY":
            target = selected_memory_target()
            return memory_embed_exact_command_review(
                target.context_name,
                target.memory_uid,
                selected_into_name(),
                gap,
                item_count=len(placement.state.rows),
                memory_selector=command_memory_selector(
                    target.context_name,
                    target.memory_uid,
                ),
                placement_selector=gap_selector,
                qualified_locator=(
                    target.context_name in setup.memory_source_granted_names
                ),
            )
        return embed_exact_command_review(
            selected_child_name(),
            selected_into_name(),
            gap,
            item_count=len(placement.state.rows),
            placement_selector=gap_selector,
        )

    def parsed_gap_position(
        target: Context,
        request: EmbedRequest | MemoryEmbedRequest,
    ) -> int:
        if request.before is not None and request.after is not None:
            raise ValueError("Pass only one of --before or --after.")
        ordered_uids = target.ordered_uids()
        if request.before is None and request.after is None:
            return len(ordered_uids)
        selector = request.before or request.after
        assert selector is not None
        anchor = ops.resolve(target, selector)
        return ordered_uids.index(anchor.uid) + (1 if request.after else 0)

    def apply_command_argv(argv: tuple[str, ...]) -> None:
        """Validate the whole edited form before changing any checked value."""

        request = parse_embed_command_argv(argv)
        into_name = resolve_displayed_command_value(
            request.into_locator,
            into_names,
            label="--into Target",
        )
        target = inspect_context(into_name)
        rows = direct_item_placement_rows(target)
        position = parsed_gap_position(target, request)
        memory_target = None
        if isinstance(request, MemoryEmbedRequest):
            source_name = resolve_displayed_command_value(
                request.source_locator,
                memory_source_names,
                label="--from Source",
            )
            memory_target = memory_source_selector.resolve_target(
                source_name,
                request.memory_selector,
            )
        else:
            child_name = resolve_displayed_command_value(
                request.child_locator,
                tuple(
                    name for name in child_names if name in setup.child_selectable_names
                ),
                label="Child ITEM",
            )
            if child_name == into_name:
                raise ValueError("Embed Child and Target must be distinct.")

        # All parsing, catalog checks, read-only loading, and anchor resolution
        # finish before these process-local controls move together.
        if memory_target is not None:
            mode.choose("MEMORY")
            memory_source_selector.select_target(memory_target)
        else:
            assert isinstance(request, EmbedRequest)
            mode.choose("CONTEXT")
            child_selector.select_name(child_name)
        into_selector.select_name(into_name)
        target_snapshot["value"] = target
        placement.replace_context(into_name, rows)
        placement.state.select_position(position)
        status["value"] = ""

    command_control = EditableExactCommandControl.create(
        ExactCommandDraft(
            review=selected_review,
            apply_argv=apply_command_argv,
            form=EMBED_COMMAND_FORM,
        ),
        action_label="PRESS ENTER TO EMBED AT THE REVIEWED GAP",
        incomplete_action="FIX THE RED COMMAND BEFORE APPLY",
        input_name="embed-proposed-command",
    )
    todo_control = command_control.input
    todo_frame = build_focused_frame(
        command_control.body,
        title=lambda: command_control.frame_title,
        is_focused=command_control.is_focused,
        height=Dimension(min=3, max=4),
    )
    # Command validity, rather than focus, is the only color signal in this
    # deliberately compact approval box.
    todo_frame.container.style = command_control.frame_style
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
        # Execution-boundary failures must remain visible while the exact
        # command owns focus; otherwise a reviewed self-link looks inert even
        # though the final freeze correctly rejected it.
        if status["value"]:
            return f" {display_escape_text(status['value'])}"
        if get_app().layout.has_focus(todo_control):
            if not command_control.valid:
                return " Enter blocked · Esc cancel"
            return " Enter run · Esc cancel"
        if get_app().layout.has_focus(into_selector.control) and placement.editing:
            return (
                " ↑/↓ move one position line · Enter/Space stage · "
                "Tab review · Esc back to Context"
            )
        if get_app().layout.has_focus(into_selector.control):
            return (
                " ↑/↓ move in Context tree · "
                "Enter/Space choose target · Tab edit position · Esc cancel"
            )
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
            command_control.sync_from_review()
        return "HANDLED"

    def move_memory_source(_event, delta: int) -> SurfaceMoveResult:
        return "MOVED" if memory_source_selector.move(delta) else "BOUNDARY"

    def choose_memory_source(_event) -> SurfaceActionResult:
        try:
            memory_source_selector.choose_cursor()
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
            command_control.sync_from_review()
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
            command_control.sync_from_review()
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
        command_control.sync_from_review()
        return "HANDLED"

    def enter_into(delta: int) -> None:
        if delta < 0:
            begin_position()
            placement.state.cursor_position = len(placement.state.rows)
            return
        placement.end()
        enter_selector(into_selector, delta)

    def finish(event) -> SurfaceActionResult:
        if not command_control.validate_current(event.app):
            status["value"] = "INVALID COMMAND · FIX THE RED EDITABLE FIELD"
            return "HANDLED"
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
                frozen_gap = DirectItemGap(
                    position=frozen.placement.position,
                    previous_uid=frozen.placement.previous_uid,
                    next_uid=frozen.placement.next_uid,
                )
                rebuilt_review = memory_embed_exact_command_review(
                    frozen.source_name,
                    frozen.memory_uid,
                    frozen.into_name,
                    frozen_gap,
                    item_count=frozen.item_count,
                    memory_selector=command_memory_selector(
                        frozen.source_name,
                        frozen.memory_uid,
                    ),
                    placement_selector=command_gap_selector(frozen_gap),
                    qualified_locator=(
                        frozen.source_name in setup.memory_source_granted_names
                    ),
                )
            else:
                frozen = freeze_exact_gap(
                    selected_child_name(),
                    target.name,
                    requested_placement,
                )
                frozen_gap = DirectItemGap(
                    position=frozen.placement.position,
                    previous_uid=frozen.placement.previous_uid,
                    next_uid=frozen.placement.next_uid,
                )
                rebuilt_review = embed_exact_command_review(
                    frozen.child_name,
                    frozen.into_name,
                    frozen_gap,
                    item_count=frozen.item_count,
                    placement_selector=command_gap_selector(frozen_gap),
                )
            if rebuilt_review != expected_review:
                raise RuntimeError(
                    "The exact Embed command changed while it was reviewed."
                )
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(result=frozen)
        return "HANDLED"

    def activate_command(event) -> SurfaceActionResult:
        return finish(event)

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        source = (
            FocusSurface(
                "CHILD",
                child_selector.control,
                move_vertical=lambda _event, delta: move_selector(
                    child_selector, delta
                ),
                activate=choose_child,
                on_vertical_enter=lambda delta: enter_selector(child_selector, delta),
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
                command_control.active_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=activate_command,
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
        or (get_app().layout.has_focus(into_selector.control) and not placement.editing)
    )
    command_input_focus = Condition(
        lambda: get_app().layout.has_focus(command_control.input)
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
        command_control.sync_from_review()
        event.app.invalidate()

    @bindings.add("right", filter=mode_focus, eager=True)
    def _next_mode(event) -> None:
        mode.move(1)
        status["value"] = ""
        command_control.sync_from_review()
        event.app.invalidate()

    @bindings.add("left", filter=memory_source_focus, eager=True)
    def _collapse_memory_source(event) -> None:
        memory_source_selector.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=memory_source_focus, eager=True)
    def _expand_memory_source(event) -> None:
        memory_source_selector.expand()
        event.app.invalidate()

    @bindings.add("a", filter=memory_source_focus, eager=True)
    @bindings.add("A", filter=memory_source_focus, eager=True)
    def _toggle_all_memory_sources(event) -> None:
        memory_source_selector.toggle_expand_all()
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

    @bindings.add(" ", filter=~command_input_focus, eager=True)
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

    @bindings.add("backspace", filter=~command_input_focus, eager=True)
    def _back(event) -> None:
        if get_app().layout.has_focus(into_selector.control) and placement.editing:
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
    app: Application[FrozenEmbedPlan | FrozenMemoryEmbedPlan | None] = Application(
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
