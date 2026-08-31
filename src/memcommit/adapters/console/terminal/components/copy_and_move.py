"""Shared interactive workbench for direct-Memory Copy and Move."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import memcommit.application.capabilities.ops as ops
from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.core.context import Context
from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.direct_memory_selector import (
    DirectMemorySelectorControl,
    DirectMemorySelectorView,
)
from memcommit.adapters.console.terminal.components.context_picker import ContextMemoryRow
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.adapters.console.terminal.components.command_editor.model import CommandReview
from memcommit.adapters.console.terminal.core.capabilities import require_interactive_terminal
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.components.direct_item_placement import (
    DirectItemGap,
    DirectItemPlacementTreeProjection,
    direct_item_placement_rows,
)
from memcommit.adapters.console.terminal.components.command_editor import (
    CommandEditorControl,
    CommandDraft,
    CommandForm,
    CommandFormField,
    resolve_displayed_command_value,
    shortest_unique_identifier_prefix,
)
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
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_tui_interrupt,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.application.operations.copy_and_move.application import (
    CopyMemoriesRequest,
    FrozenCopyMemoriesPlan,
    FrozenMoveMemoriesPlan,
    MemoryTransferPlacement,
    MoveMemoriesRequest,
    validate_copy_request,
    validate_move_request,
)
from memcommit.adapters.console.coordination.copy_and_move.model import (
    CopyAndMoveTuiSetup,
)


COPY_COMMAND_FORM = CommandForm(
    command=("mem", "copy"),
    usage="mem copy MEMORY... --into TARGET [--before ITEM | --after ITEM]",
    fields=(
        CommandFormField(
            "MEMORY... | -m MEMORY...",
            "choose one or more direct Memory locators in transfer order",
        ),
        CommandFormField(
            "--from SOURCE",
            "apply one direct owner to every unqualified Memory selector",
        ),
        CommandFormField(
            "--into TARGET",
            "choose the one local Context whose direct order changes",
        ),
        CommandFormField(
            "--before ITEM | --after ITEM",
            "choose one adjacent direct-item gap; omit to append",
        ),
    ),
)


MOVE_COMMAND_FORM = CommandForm(
    command=("mem", "move"),
    usage=(
        "mem move MEMORY... --into TARGET [--before ITEM | --after ITEM] "
        "[--break-links]"
    ),
    fields=(
        CommandFormField(
            "MEMORY... | -m MEMORY...",
            "choose one or more directly owned Memories in transfer order",
        ),
        CommandFormField(
            "--from SOURCE",
            "apply one direct owner to every unqualified Memory selector",
        ),
        CommandFormField(
            "--into TARGET",
            "choose the new local direct owner",
        ),
        CommandFormField(
            "--before ITEM | --after ITEM",
            "choose one adjacent direct-item gap; omit to append",
        ),
        CommandFormField(
            "--break-links",
            "advanced opt-in: leave inbound live Memory Embeds dangling",
        ),
    ),
)


def parse_copy_and_move_command_argv(
    argv: Sequence[str],
    *,
    kind: str,
) -> CopyMemoriesRequest | MoveMemoriesRequest:
    """Parse the editable Copy/Move subset without invoking a nested CLI."""

    operation = kind.upper()
    if operation not in {"COPY", "MOVE"}:
        raise ValueError("Copy/Move kind must be COPY or MOVE.")
    expected = ("mem", operation.lower())
    values = tuple(argv)
    if values[:2] != expected:
        raise ValueError(
            f"Editable {operation.title()} commands must start with "
            f"'mem {operation.lower()}'."
        )
    operands: list[str] = []
    memory_options: list[str] = []
    options: dict[str, str] = {}
    switches: set[str] = set()
    value_flags = {"--memory", "-m", "--from", "--into", "--to", "--before", "--after"}
    switch_flags = (
        set()
        if operation == "COPY"
        else {"--retarget-links", "--break-links"}
    )
    index = 2
    while index < len(values):
        value = values[index]
        if value in switch_flags:
            if value in switches:
                raise ValueError(f"{operation.title()} flag '{value}' may be supplied only once.")
            switches.add(value)
            index += 1
            continue
        if value in value_flags:
            if index + 1 >= len(values) or values[index + 1].startswith("--"):
                raise ValueError(f"{operation.title()} flag '{value}' requires one value.")
            next_value = values[index + 1]
            if value in {"--memory", "-m"}:
                memory_options.append(next_value)
            else:
                if value in options:
                    raise ValueError(
                        f"{operation.title()} flag '{value}' may be supplied only once."
                    )
                options[value] = next_value
            index += 2
            continue
        if value.startswith("-"):
            raise ValueError(f"Unknown {operation.title()} flag '{value}'.")
        operands.append(value)
        index += 1

    if operands and memory_options:
        raise ValueError("Use positional MEMORY locators or repeat --memory, not both.")
    locators = tuple(operands or memory_options)
    if not locators:
        raise ValueError("Editable Copy/Move requires one or more Memories.")
    if "--into" in options and "--to" in options:
        raise ValueError("Use only one of --into or --to.")
    into = options.get("--into") or options.get("--to")
    if into is None:
        raise ValueError("Editable Copy/Move requires --into TARGET.")
    if "--before" in options and "--after" in options:
        raise ValueError("Pass only one of --before or --after.")
    if operation == "COPY":
        return validate_copy_request(
            CopyMemoriesRequest(
                memory_locators=locators,
                source_locator=options.get("--from"),
                into_locator=into,
                before=options.get("--before"),
                after=options.get("--after"),
            )
        )
    if "--retarget-links" in switches and "--break-links" in switches:
        raise ValueError("Pass only one of --retarget-links or --break-links.")
    return validate_move_request(
        MoveMemoriesRequest(
            memory_locators=locators,
            source_locator=options.get("--from"),
            into_locator=into,
            before=options.get("--before"),
            after=options.get("--after"),
            # Live Embeds follow ownership by default.  The retained
            # --retarget-links spelling is therefore a compatibility no-op.
            link_policy=("BREAK" if "--break-links" in switches else "RETARGET"),
        )
    )


def _placement_argv(gap: DirectItemGap, *, selector: str | None) -> tuple[str, ...]:
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


def copy_and_move_exact_command_review(
    request: CopyMemoriesRequest | MoveMemoriesRequest,
    gap: DirectItemGap,
    *,
    item_count: int,
    placement_selector: str | None = None,
) -> CommandReview:
    """Build one exact command and its complete visible effect boundary."""

    if request.into_locator is None:
        raise ValueError("Select one Target Context first.")
    count = len(request.memory_locators)
    noun = "Memory" if count == 1 else "Memories"
    placement = _placement_argv(gap, selector=placement_selector)
    if isinstance(request, CopyMemoriesRequest):
        effects = (
            f"Copy {count} direct Source {noun} into '{request.into_locator}'.",
            (
                "Owned or READ-granted Sources stay unchanged; outputs "
                "receive new independent local UIDs."
            ),
            _gap_effect(gap, item_count),
        )
        argv = (
            "mem",
            "copy",
            *request.memory_locators,
            "--into",
            request.into_locator,
            *placement,
        )
    else:
        effects = (
            f"Move {count} directly owned {noun} into '{request.into_locator}'.",
            (
                "Live Memory Embeds may remain dangling by explicit request; snapshots stay unchanged."
                if request.link_policy == "BREAK"
                else "Every local live Memory Embed follows atomically; snapshots stay unchanged."
            ),
            _gap_effect(gap, item_count),
        )
        argv = (
            "mem",
            "move",
            *request.memory_locators,
            "--into",
            request.into_locator,
            *placement,
            *(("--break-links",) if request.link_policy == "BREAK" else ()),
        )
    return CommandReview(argv=argv, effects=effects)


def run_copy_and_move_workbench(
    setup: CopyAndMoveTuiSetup,
    *,
    kind: str,
    inspect_source_context: Callable[[str], Context],
    inspect_into_context: Callable[[str], Context],
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]],
    freeze_copy: Callable[[CopyMemoriesRequest], FrozenCopyMemoriesPlan],
    freeze_move: Callable[[MoveMemoriesRequest], FrozenMoveMemoriesPlan],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenCopyMemoriesPlan | FrozenMoveMemoriesPlan | None:
    """Choose multiple Sources, one Target gap, and one exact transfer command."""

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
    local_source_names = setup.local_source_names
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
    move_break = {"value": False}
    status = {"value": ""}
    bindings = KeyBindings()

    def selected_into_name() -> str:
        return into_selector.selection.selected_name

    def memory_selector(target: DirectMemoryTarget) -> str:
        rows = source_selector.preview.memory_cache.get(target.context_name, ())
        candidates = tuple(row.selector for row in rows if row.selector is not None)
        return shortest_unique_identifier_prefix(
            target.memory_uid,
            candidates,
            minimum=7,
        )

    def qualified_locator(target: DirectMemoryTarget) -> str:
        return f"{target.context_name}:{memory_selector(target)}"

    def command_gap_selector(gap: DirectItemGap) -> str | None:
        anchor = gap.next_uid or gap.previous_uid
        if anchor is None:
            return None
        return shortest_unique_identifier_prefix(
            anchor,
            tuple(row.uid for row in placement.state.rows),
            minimum=7,
        )

    def selected_request() -> CopyMemoriesRequest | MoveMemoriesRequest:
        selected = source_selector.selected_many
        if not selected:
            raise ValueError("Select one or more direct Source Memories first.")
        gap = placement.state.selected_gap
        placement_argv = _placement_argv(
            gap,
            selector=command_gap_selector(gap),
        )
        before = placement_argv[1] if placement_argv[:1] == ("--before",) else None
        after = placement_argv[1] if placement_argv[:1] == ("--after",) else None
        locators = tuple(qualified_locator(target) for target in selected)
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
                link_policy="BREAK" if move_break["value"] else "RETARGET",
            )
        )

    def selected_review() -> CommandReview:
        gap = placement.state.selected_gap
        return copy_and_move_exact_command_review(
            selected_request(),
            gap,
            item_count=len(placement.state.rows),
            placement_selector=command_gap_selector(gap),
        )

    def parsed_gap_position(
        target: Context,
        request: CopyMemoriesRequest | MoveMemoriesRequest,
    ) -> int:
        order = target.ordered_uids()
        if request.before is None and request.after is None:
            return len(order)
        selector = request.before or request.after
        assert selector is not None
        anchor = ops.resolve(target, selector)
        return order.index(anchor.uid) + (1 if request.after is not None else 0)

    def resolve_command_target(
        locator: str,
        *,
        explicit_source: str | None,
    ) -> DirectMemoryTarget:
        parsed = parse_direct_memory_locator(locator, explicit_context=explicit_source)
        if parsed.context_locator is not None:
            context_name = resolve_displayed_command_value(
                parsed.context_locator,
                source_names,
                label="Source Context",
            )
            return source_selector.resolve_target(context_name, parsed.memory_selector)
        # A bare UID is intentionally local-only. Grant content becomes a
        # Source only through its reviewed public owner (`PUBLIC:UID` or
        # `--from PUBLIC`) so editing the exact command cannot silently widen
        # the authority namespace that was searched.
        matches: list[DirectMemoryTarget] = []
        for context_name in local_source_names:
            try:
                matches.append(
                    source_selector.resolve_target(context_name, parsed.memory_selector)
                )
            except ValueError as error:
                if "No directly owned Memory matches" not in str(error):
                    raise
        if not matches:
            raise ValueError(
                f"No directly owned Memory matches '{parsed.memory_selector}' "
                "in the frozen local catalog."
            )
        if len(matches) > 1:
            raise ValueError(
                f"Memory selector '{parsed.memory_selector}' is ambiguous; "
                "use CONTEXT:UID."
            )
        return matches[0]

    def apply_command_argv(argv: tuple[str, ...]) -> None:
        """Validate the complete edited form before moving any local control."""

        request = parse_copy_and_move_command_argv(argv, kind=operation)
        assert request.into_locator is not None
        into_name = resolve_displayed_command_value(
            request.into_locator,
            into_names,
            label="--into Target",
        )
        explicit_source = (
            resolve_displayed_command_value(
                request.source_locator,
                source_names,
                label="--from Source",
            )
            if request.source_locator is not None
            else None
        )
        targets = tuple(
            resolve_command_target(locator, explicit_source=explicit_source)
            for locator in request.memory_locators
        )
        if len(set(targets)) != len(targets):
            raise ValueError("A Source Memory may be selected only once.")
        target = inspect_into_context(into_name)
        rows = direct_item_placement_rows(target)
        position = parsed_gap_position(target, request)

        # Parsing, catalog checks, all Memory resolution, and gap resolution
        # finish before these process-local controls move as one form update.
        source_selector.replace_targets(targets)
        into_selector.select_name(into_name)
        target_snapshot["value"] = target
        placement.replace_context(into_name, rows)
        placement.state.select_position(position)
        if isinstance(request, MoveMemoriesRequest):
            move_break["value"] = request.link_policy == "BREAK"
        status["value"] = ""

    command_control = CommandEditorControl.create(
        CommandDraft(
            review=selected_review,
            apply_argv=apply_command_argv,
            form=(COPY_COMMAND_FORM if operation == "COPY" else MOVE_COMMAND_FORM),
        ),
        action_label=f"PRESS ENTER TO {operation} AT THE REVIEWED GAP",
        incomplete_action="FIX THE RED COMMAND BEFORE APPLY",
        input_name=f"{operation.lower()}-proposed-command",
    )
    command_frame = build_focused_frame(
        command_control.body,
        title=lambda: command_control.frame_title,
        is_focused=command_control.is_focused,
        height=Dimension(min=3, max=4),
    )
    command_frame.container.style = command_control.frame_style
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
                    " · LIVE EMBEDS FOLLOW"
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
        if get_app().layout.has_focus(command_control.input):
            if not command_control.valid:
                return " Enter blocked · Esc cancel"
            if operation == "MOVE":
                return (
                    " Enter run · BREAK LINKS may dangle live Embeds · "
                    "snapshots stay · Esc cancel"
                    if move_break["value"]
                    else " Enter run · live Embeds follow atomically · "
                    "snapshots stay · Esc cancel"
                )
            return " Enter run · Esc cancel"
        if get_app().layout.has_focus(into_selector.control) and placement.editing:
            return (
                " ↑/↓ move one position line · Enter/Space stage · "
                "Tab review · Esc back to Context"
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
            command_control.sync_from_review()
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
        command_control.sync_from_review()
        return "HANDLED"

    def enter_into(delta: int) -> None:
        if delta < 0:
            begin_position()
            placement.state.cursor_position = len(placement.state.rows)
            return
        placement.end()
        enter_context(into_selector, delta)

    def finish(event) -> SurfaceActionResult:
        if not command_control.validate_current(event.app):
            status["value"] = "INVALID COMMAND · FIX THE RED EDITABLE FIELD"
            return "HANDLED"
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
            frozen = (
                freeze_copy(request)
                if isinstance(request, CopyMemoriesRequest)
                else freeze_move(request)
            )
            if frozen.placement != expected_placement:
                raise RuntimeError(
                    f"The exact {operation.title()} gap changed while it was reviewed."
                )
        except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as error:
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
                FocusSurface(
                    "COMMAND",
                    command_control.active_control,
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

    source_focus = Condition(lambda: get_app().layout.has_focus(source_selector.control))
    target_focus = Condition(
        lambda: get_app().layout.has_focus(into_selector.control)
        and not placement.editing
    )
    command_focus = Condition(lambda: get_app().layout.has_focus(command_control.input))

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

    @bindings.add(" ", filter=~command_focus, eager=True)
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

    @bindings.add("backspace", filter=~command_focus, eager=True)
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
            TuiRegion(command_frame),
            TuiRegion(footer),
        )
    )
    root = build_tui_frame(*regions)
    app: Application[
        FrozenCopyMemoriesPlan | FrozenMoveMemoriesPlan | None
    ] = Application(
        layout=Layout(root, focused_element=source_selector.control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    return app.run()


__all__ = [
    "COPY_COMMAND_FORM",
    "MOVE_COMMAND_FORM",
    "copy_and_move_exact_command_review",
    "parse_copy_and_move_command_argv",
    "run_copy_and_move_workbench",
]
