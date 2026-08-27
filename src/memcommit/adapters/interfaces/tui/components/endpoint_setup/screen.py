"""Shared mode and Context-role setup screen for rebuilt TUI operations."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
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

from memcommit.core.context_targeting.tui.reach import (
    ContextReachState,
    render_context_reach,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.core.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.adapters.interfaces.console.terminal import require_interactive_terminal
from memcommit.adapters.interfaces.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.components.endpoint_setup.compact_screen import (
    run_compact_endpoint_setup,
)
from memcommit.adapters.interfaces.tui.components.endpoint_setup.memory_focus import (
    EndpointMemoryFocusController,
    MemoryProjectionLoader,
)
from memcommit.adapters.interfaces.tui.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupSpec,
    EndpointSetupValue,
)
from memcommit.adapters.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.application.exact_command_review import ExactCommandReview
from memcommit.adapters.interfaces.tui.components.exact_command_review.rendering import (
    format_exact_command,
)
from memcommit.adapters.interfaces.tui.components.exact_name import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.adapters.interfaces.console.selection import FlatSelectionState, SelectionOption
from memcommit.adapters.interfaces.console.selection.tui import render_vertical_choice_rows


DraftValidator = Callable[[EndpointSetupDraft], str | None]
CommandReviewBuilder = Callable[[EndpointSetupDraft], ExactCommandReview]


def run_endpoint_setup(
    spec: EndpointSetupSpec,
    *,
    memory_loader: MemoryProjectionLoader | None = None,
    validate_draft: DraftValidator | None = None,
    command_review: CommandReviewBuilder | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> EndpointSetupDraft | None:
    """Collect a typed shape through caller-authorized read-only projections."""

    if not isinstance(spec, EndpointSetupSpec):
        raise TypeError("Endpoint setup requires an EndpointSetupSpec.")
    if spec.screen_layout == "COMPACT_FORM":
        return run_compact_endpoint_setup(
            spec,
            memory_loader=memory_loader,
            validate_draft=validate_draft,
            command_review=command_review,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
    if require_tty:
        require_interactive_terminal(
            spec.title,
            snapshot_hint="Pass explicit Context operands outside a terminal.",
        )

    mode_state = FlatSelectionState(
        options=tuple(
            SelectionOption(mode.uid, mode.label, mode.description)
            for mode in spec.modes
        ),
        cursor_uid=spec.initial_mode_uid,
        selected_uid=spec.initial_mode_uid,
        allow_empty=False,
    )

    def selected_mode_uid() -> str:
        selected = mode_state.selected_uid
        if selected is None:
            raise ValueError("Choose one operation shape.")
        return selected

    def role_is_active(role_uid: str) -> bool:
        return role_uid in spec.active_role_uids(selected_mode_uid())

    def role_allows_descendants(role_uid: str) -> bool:
        return spec.role_allows_descendants(selected_mode_uid(), role_uid)

    def role_allows_memory_focus(role_uid: str) -> bool:
        return spec.role_allows_memory_focus(selected_mode_uid(), role_uid)

    selectors: dict[str, ContextSelectorControl] = {}
    for role in spec.roles:
        if not role.selectable_names:
            continue
        selector = ContextSelectorControl(
            ContextSelectorView(
                names=role.names,
                selected=(role.selected_name,),
                label=role.label,
                current_context=role.current_context,
                selectable_names=role.selectable_names,
                annotations=role.annotations,
            ),
            height=role.height,
        )
        selector.frame.title = lambda uid=role.uid: safe_terminal_text(
            spec.role_label(selected_mode_uid(), uid)
            + (" · FIXED" if role_by_uid[uid].fixed else "")
        )
        selectors[role.uid] = selector
    reach_states = {
        role.uid: ContextReachState.create(include_descendants=role.include_descendants)
        for role in spec.roles
        if role.allow_descendants
    }
    memory_roles = tuple(role for role in spec.roles if role.allow_memory_focus)
    if memory_roles and memory_loader is None:
        raise ValueError("Endpoint Memory focus requires a projection loader.")
    memory_focuses: dict[str, EndpointMemoryFocusController] = {}
    if memory_loader is not None:
        memory_focuses = {
            role.uid: EndpointMemoryFocusController(
                role_uid=role.uid,
                selected_context=lambda uid=role.uid: selectors[
                    uid
                ].selection.selected_name,
                loader=memory_loader,
                selected_memory_uid=role.selected_memory_uid,
            )
            for role in memory_roles
        }
    bindings = KeyBindings()
    status = {"value": ""}
    role_by_uid = {role.uid: role for role in spec.roles}
    create_new = {role.uid: role.prefer_new for role in spec.roles if role.allow_new}
    confirmed_new_names = {
        role.uid: role.initial_new_name.strip() for role in spec.roles if role.allow_new
    }
    new_name_fields: dict[str, ExactNameFieldControl] = {}
    for role in spec.roles:
        if not role.allow_new:
            continue

        def validate_new_name(
            candidate: str,
            *,
            names=role.names,
            operation_validator=role.new_name_validator,
        ) -> None:
            validate_portable_context_name(candidate)
            if candidate in names:
                raise ValueError(
                    "That Context already exists; choose its available tree row."
                )
            if operation_validator is not None:
                operation_validator(candidate)

        new_name_fields[role.uid] = ExactNameFieldControl.create(
            ExactNameFieldView(
                value=role.initial_new_name,
                label=role.new_label,
                state="CREATE ON START",
                detail="Enter confirms this exact Result Context name.",
                validate=validate_new_name,
                value_label="Context name",
            ),
            input_name=f"endpoint-{role.uid.casefold()}-new-name",
        )

    mode_control = FormattedTextControl(
        lambda: render_vertical_choice_rows(
            mode_state,
            focused=get_app().layout.has_focus(mode_control),
            content_width=84,
            numbered=False,
        ),
        focusable=True,
        show_cursor=False,
    )
    mode_height = max(4, 3 * len(spec.modes) + 2)
    mode_frame = build_focused_frame(
        Window(mode_control, wrap_lines=True),
        title="OPERATION SHAPE",
        is_focused=lambda: get_app().layout.has_focus(mode_control),
        height=Dimension.exact(mode_height),
    )
    reach_controls: dict[str, FormattedTextControl] = {}
    reach_frames = {}
    for role in spec.roles:
        if not role.allow_descendants:
            continue
        control: FormattedTextControl

        def render_reach(uid=role.uid):
            return render_context_reach(
                reach_states[uid],
                title="",
                focused=get_app().layout.has_focus(reach_controls[uid]),
            )

        control = FormattedTextControl(
            render_reach,
            focusable=True,
            show_cursor=False,
        )
        reach_controls[role.uid] = control
        reach_frames[role.uid] = build_focused_frame(
            Window(control, height=Dimension.exact(1), dont_extend_height=True),
            title=lambda uid=role.uid: (
                f"{safe_terminal_text(spec.role_label(selected_mode_uid(), uid))}"
                " · RANGE"
            ),
            is_focused=lambda uid=role.uid: get_app().layout.has_focus(
                reach_controls[uid]
            ),
            height=Dimension.exact(3),
        )

    memory_controls: dict[str, FormattedTextControl] = {}
    memory_frames = {}
    for role in spec.roles:
        if not role.allow_memory_focus:
            continue
        memory_control: FormattedTextControl

        def render_memory(uid=role.uid):
            focused = get_app().layout.has_focus(memory_controls[uid])
            return memory_focuses[uid].render(
                focused=focused,
                include_descendants=(
                    reach_states[uid].include_descendants
                    if uid in reach_states
                    else False
                ),
            )

        memory_control = FormattedTextControl(
            render_memory,
            focusable=True,
            show_cursor=False,
        )
        memory_controls[role.uid] = memory_control
        memory_frames[role.uid] = build_focused_frame(
            Window(
                memory_control,
                wrap_lines=True,
                right_margins=[ScrollbarMargin(display_arrows=True)],
            ),
            title=lambda uid=role.uid: (
                f"{safe_terminal_text(spec.role_label(selected_mode_uid(), uid))}"
                + (
                    " · MEMORY PREVIEW"
                    if role_by_uid[uid].memory_preview_only
                    else " · MEMORY FOCUS"
                )
            ),
            is_focused=lambda uid=role.uid: get_app().layout.has_focus(
                memory_controls[uid]
            ),
            height=Dimension.exact(role.memory_height),
        )

    def make_draft() -> EndpointSetupDraft:
        selected_mode = mode_state.selected_uid
        if selected_mode is None:
            raise ValueError("Choose one operation shape.")
        active_role_uids = spec.active_role_uids(selected_mode)

        def make_value(role_uid: str) -> EndpointSetupValue:
            role = role_by_uid[role_uid]
            if role.allow_new and create_new[role_uid]:
                candidate = new_name_fields[role_uid].text.strip()
                if not candidate or confirmed_new_names[role_uid] != candidate:
                    raise ValueError(
                        f"Confirm {role.new_label} with Enter before continuing."
                    )
                candidate = new_name_fields[role_uid].validate_candidate()
                return EndpointSetupValue(
                    role_uid,
                    candidate,
                    create=True,
                )
            if role_uid not in selectors:
                raise ValueError(f"{role.new_label} requires a new exact name.")
            return EndpointSetupValue(
                role_uid,
                selectors[role_uid].selection.selected_name,
                include_descendants=(
                    reach_states[role_uid].include_descendants
                    if role_uid in reach_states and role_allows_descendants(role_uid)
                    else False
                ),
                memory_uid=(
                    memory_focuses[role_uid].selected_memory_uid
                    if role_uid in memory_focuses
                    and role_allows_memory_focus(role_uid)
                    and not role.memory_preview_only
                    else None
                ),
            )

        return EndpointSetupDraft(
            mode_uid=selected_mode,
            values=tuple(make_value(role_uid) for role_uid in active_role_uids),
        )

    def checked_draft() -> EndpointSetupDraft:
        draft = make_draft()
        message = validate_draft(draft) if validate_draft is not None else None
        if message:
            raise ValueError(message)
        return draft

    def render_command() -> list[tuple[str, str]]:
        if command_review is None:
            return []
        try:
            review = command_review(checked_draft())
        except (OSError, TypeError, ValueError) as error:
            return [
                ("class:error", "COMMAND · INVALID\n"),
                ("class:error", f"{safe_terminal_text(str(error))}\n\n"),
            ]
        return [
            ("class:report-label", "COMMAND · RUNNABLE\n"),
            ("class:report-neutral", f"{format_exact_command(review)}\n\n"),
        ]

    def render_action() -> list[tuple[str, str]]:
        mode_uid = selected_mode_uid()
        focused = get_app().layout.has_focus(action_control)
        fragments: list[tuple[str, str]] = [
            ("class:report-label", "SELECTIONS READY\n"),
            ("class:report-neutral", f"MODE · {safe_terminal_text(mode_uid)}\n"),
        ]
        for role_uid in spec.active_role_uids(mode_uid):
            role = role_by_uid[role_uid]
            is_new = role.allow_new and create_new[role_uid]
            context_name = (
                new_name_fields[role_uid].text.strip() or "(ENTER EXACT NAME)"
                if is_new
                else selectors[role_uid].selection.selected_name
            )
            include_descendants = (
                reach_states[role_uid].include_descendants
                if role_uid in reach_states and role_allows_descendants(role_uid)
                else False
            )
            memory_uid = (
                memory_focuses[role_uid].selected_memory_uid
                if role_uid in memory_focuses
                and role_allows_memory_focus(role_uid)
                and not role.memory_preview_only
                else None
            )
            range_suffix = (
                " · INCLUDE DESCENDANTS"
                if include_descendants
                else " · THIS CONTEXT ONLY"
            )
            if not role_allows_descendants(role_uid):
                range_suffix = ""
            memory_suffix = ""
            if role_allows_memory_focus(role_uid):
                memory_suffix = (
                    " · READ-ONLY MEMORY PREVIEW"
                    if role.memory_preview_only
                    else f" · MEMORY {safe_terminal_text(memory_uid[:8])}"
                    if memory_uid is not None
                    else " · WHOLE CONTEXT"
                )
                if include_descendants:
                    memory_suffix = ""
            fragments.append(
                (
                    "class:report-neutral",
                    f"{safe_terminal_text(role_uid)} · "
                    f"{safe_terminal_text(context_name)}"
                    f"{range_suffix}{memory_suffix}"
                    f"{' · NEW · CREATE ON START' if is_new else ''}\n",
                )
            )
        fragments.extend(
            [
                ("", "\n"),
                *render_command(),
                ("[SetCursorPosition]", "") if focused else ("", ""),
                (
                    focused_control_style(focused=focused),
                    f"[ {safe_terminal_text(spec.action_label)} ]",
                ),
            ]
        )
        return fragments

    action_control = FormattedTextControl(
        render_action,
        focusable=True,
        show_cursor=False,
    )
    action_frame = build_focused_frame(
        Window(action_control, wrap_lines=True),
        title="TO DO",
        is_focused=lambda: get_app().layout.has_focus(action_control),
        height=Dimension(min=9, weight=1),
    )
    header = Window(
        FormattedTextControl(
            f" {safe_terminal_text(spec.title)}\n {safe_terminal_text(spec.subtitle)}"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    editable_roles = tuple(
        role for role in spec.roles if not role.fixed and role.uid in selectors
    )
    editable_controls = tuple(selectors[role.uid].control for role in editable_roles)

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if get_app().layout.has_focus(mode_control):
            return " ←/→ or ↑/↓ choose shape · Tab endpoint · Esc cancel"
        if get_app().layout.has_focus(action_control):
            return " Enter run selected setup · ↑ endpoint · Esc cancel"
        if any(
            get_app().layout.has_focus(control) for control in reach_controls.values()
        ):
            return " ←/→ choose this Context only or include descendants · Tab next · Esc cancel"
        if any(
            get_app().layout.has_focus(control) for control in memory_controls.values()
        ):
            return " ↑/↓ choose whole Context or one direct Memory · Enter select · Tab next · Esc cancel"
        if any(
            get_app().layout.has_focus(field.input)
            for field in new_name_fields.values()
        ):
            return " Type one exact new Context name · Enter confirm · Tab next · Esc cancel"
        return " ↑/↓ move/cross · ←/→ tree · Enter/Space select · Tab next · Esc cancel"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    role_regions: list[TuiRegion] = []
    for role in spec.roles:
        if role.uid in selectors:
            role_regions.append(
                TuiRegion(
                    ConditionalContainer(
                        selectors[role.uid].frame,
                        filter=Condition(lambda uid=role.uid: role_is_active(uid)),
                    )
                )
            )
        if role.uid in reach_frames:
            role_regions.append(
                TuiRegion(
                    ConditionalContainer(
                        reach_frames[role.uid],
                        filter=Condition(
                            lambda uid=role.uid: role_is_active(uid)
                            and role_allows_descendants(uid)
                        ),
                    )
                )
            )
        if role.uid in memory_frames:
            role_regions.append(
                TuiRegion(
                    ConditionalContainer(
                        memory_frames[role.uid],
                        filter=Condition(
                            lambda uid=role.uid: role_is_active(uid)
                            and role_allows_memory_focus(uid)
                        ),
                    )
                )
            )
        if role.uid in new_name_fields:
            role_regions.append(
                TuiRegion(
                    ConditionalContainer(
                        new_name_fields[role.uid].frame,
                        filter=Condition(lambda uid=role.uid: role_is_active(uid)),
                    )
                )
            )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(mode_frame),
        *role_regions,
        TuiRegion(action_frame),
        TuiRegion(footer),
    )
    preferred_new_control = next(
        (
            new_name_fields[role.uid].input
            for role in spec.roles
            if role.allow_new and role.prefer_new and role_is_active(role.uid)
        ),
        None,
    )
    initial_focus = (
        mode_control
        if len(spec.modes) > 1
        else preferred_new_control
        or (editable_controls[0] if editable_controls else mode_control)
    )
    app: Application[EndpointSetupDraft | None] = Application(
        layout=Layout(root, focused_element=initial_focus),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_mode(_event, delta: int) -> SurfaceMoveResult:
        changed = mode_state.move(delta)
        mode_state.set_selected(mode_state.cursor_uid)
        for uid, memory_focus in memory_focuses.items():
            if not role_allows_memory_focus(uid):
                memory_focus.clear()
        status["value"] = ""
        return "MOVED" if changed else "BOUNDARY"

    def choose_mode(_event) -> SurfaceActionResult:
        mode_state.select_cursor(toggle=False)
        for uid, memory_focus in memory_focuses.items():
            if not role_allows_memory_focus(uid):
                memory_focus.clear()
        status["value"] = ""
        return "HANDLED"

    def move_role(role_uid: str, delta: int) -> SurfaceMoveResult:
        selector = selectors[role_uid]
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def enter_role(role_uid: str, delta: int) -> None:
        rows = selectors[role_uid].tree.visible_rows()
        selectors[role_uid].tree.selected_name = rows[0 if delta > 0 else -1].name

    def choose_role(role_uid: str) -> SurfaceActionResult:
        try:
            candidate = selectors[role_uid].tree.selected_name
            if candidate not in role_by_uid[role_uid].selectable_names:
                raise ValueError("That Context is unavailable for this role.")
            if role_uid in memory_focuses:
                memory_focuses[role_uid].prepare_context(candidate)
            selectors[role_uid].choose_cursor()
        except ValueError as error:
            status["value"] = str(error)
        else:
            if role_uid in create_new:
                create_new[role_uid] = False
            if role_uid in memory_focuses:
                memory_focuses[role_uid].clear()
            status["value"] = ""
        return "HANDLED"

    def confirm_new_name(event, role_uid: str) -> SurfaceActionResult:
        try:
            candidate = new_name_fields[role_uid].validate_candidate()
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"
        confirmed_new_names[role_uid] = candidate
        create_new[role_uid] = True
        if role_uid in memory_focuses:
            memory_focuses[role_uid].clear()
        if role_uid in reach_states:
            reach_states[role_uid] = ContextReachState.create(include_descendants=False)
        status["value"] = f"{candidate} will be created when this operation starts."
        surfaces.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def move_memory(role_uid: str, delta: int) -> SurfaceMoveResult:
        if role_uid in reach_states and reach_states[role_uid].include_descendants:
            return "BOUNDARY"
        changed = memory_focuses[role_uid].move(delta)
        status["value"] = ""
        return "MOVED" if changed else "BOUNDARY"

    def enter_memory(role_uid: str, delta: int) -> None:
        memory_focuses[role_uid].enter(delta)

    def choose_memory(role_uid: str) -> SurfaceActionResult:
        if role_uid in reach_states and reach_states[role_uid].include_descendants:
            memory_focuses[role_uid].clear()
            status["value"] = "Focused Memory requires THIS CONTEXT ONLY."
            return "HANDLED"
        if role_by_uid[role_uid].memory_preview_only:
            status["value"] = (
                "Memory rows are read-only evidence; the whole Context remains selected."
            )
            return "HANDLED"
        memory_focuses[role_uid].choose()
        status["value"] = ""
        return "HANDLED"

    def finish(event) -> SurfaceActionResult:
        try:
            draft = checked_draft()
            if command_review is not None:
                command_review(draft)
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(result=draft)
        return "HANDLED"

    editable_role_uids = {role.uid for role in editable_roles}

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        values: list[FocusSurface] = [
            FocusSurface(
                "MODE",
                mode_control,
                move_vertical=move_mode,
                activate=choose_mode,
            )
        ]
        for role_uid in spec.active_role_uids(selected_mode_uid()):
            if role_uid in editable_role_uids:
                values.append(
                    FocusSurface(
                        f"ROLE:{role_uid}",
                        selectors[role_uid].control,
                        move_vertical=lambda _event, delta, uid=role_uid: move_role(
                            uid, delta
                        ),
                        activate=lambda _event, uid=role_uid: choose_role(uid),
                        on_vertical_enter=lambda delta, uid=role_uid: enter_role(
                            uid, delta
                        ),
                    )
                )
            if role_uid in reach_controls and role_allows_descendants(role_uid):
                values.append(
                    FocusSurface(
                        f"RANGE:{role_uid}",
                        reach_controls[role_uid],
                        move_vertical=lambda _event, _delta: "BOUNDARY",
                    )
                )
            if role_uid in memory_controls and role_allows_memory_focus(role_uid):
                values.append(
                    FocusSurface(
                        f"MEMORY:{role_uid}",
                        memory_controls[role_uid],
                        move_vertical=lambda _event, delta, uid=role_uid: move_memory(
                            uid, delta
                        ),
                        activate=lambda _event, uid=role_uid: choose_memory(uid),
                        on_vertical_enter=lambda delta, uid=role_uid: enter_memory(
                            uid, delta
                        ),
                    )
                )
            if role_uid in new_name_fields:
                values.append(
                    FocusSurface(
                        f"NEW:{role_uid}",
                        new_name_fields[role_uid].input,
                        activate=lambda event, uid=role_uid: confirm_new_name(
                            event, uid
                        ),
                    )
                )
        values.append(
            FocusSurface(
                "CONTINUE",
                action_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=finish,
            )
        )
        return tuple(values)

    surfaces = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("left", filter=has_focus(mode_control), eager=True)
    def _mode_left(event) -> None:
        move_mode(event, -1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(mode_control), eager=True)
    def _mode_right(event) -> None:
        move_mode(event, 1)
        event.app.invalidate()

    reach_focus = Condition(
        lambda: any(
            get_app().layout.has_focus(control) for control in reach_controls.values()
        )
    )

    def focused_reach_role_uid() -> str | None:
        return next(
            (
                uid
                for uid, control in reach_controls.items()
                if get_app().layout.has_focus(control)
            ),
            None,
        )

    def move_reach(delta: int) -> None:
        uid = focused_reach_role_uid()
        if uid is not None:
            was_descendants = reach_states[uid].include_descendants
            reach_states[uid].move(delta)
            if (
                not was_descendants
                and reach_states[uid].include_descendants
                and uid in memory_focuses
                and memory_focuses[uid].clear()
            ):
                # A subtree may still contain the Memory, but retaining its UID
                # would silently narrow the executable draft behind broader UI.
                status["value"] = (
                    f"{role_by_uid[uid].label} Memory focus cleared for descendants."
                )
            else:
                status["value"] = ""

    @bindings.add("left", filter=reach_focus, eager=True)
    def _reach_left(event) -> None:
        move_reach(-1)
        event.app.invalidate()

    @bindings.add("right", filter=reach_focus, eager=True)
    def _reach_right(event) -> None:
        move_reach(1)
        event.app.invalidate()

    editable_focus = Condition(
        lambda: any(
            get_app().layout.has_focus(control) for control in editable_controls
        )
    )
    memory_focus = Condition(
        lambda: any(
            get_app().layout.has_focus(control) for control in memory_controls.values()
        )
    )
    new_input_focus = Condition(
        lambda: any(
            get_app().layout.has_focus(field.input)
            for field in new_name_fields.values()
        )
    )

    def focused_role_uid() -> str | None:
        return next(
            (
                role.uid
                for role in editable_roles
                if get_app().layout.has_focus(selectors[role.uid].control)
            ),
            None,
        )

    @bindings.add("left", filter=editable_focus, eager=True)
    def _collapse(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            selectors[uid].collapse()
        event.app.invalidate()

    @bindings.add("right", filter=editable_focus, eager=True)
    def _expand(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            selectors[uid].expand()
        event.app.invalidate()

    @bindings.add(" ", filter=editable_focus, eager=True)
    def _choose(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            choose_role(uid)
        event.app.invalidate()

    @bindings.add(" ", filter=memory_focus, eager=True)
    def _choose_memory(event) -> None:
        uid = next(
            (
                role_uid
                for role_uid, control in memory_controls.items()
                if get_app().layout.has_focus(control)
            ),
            None,
        )
        if uid is not None:
            choose_memory(uid)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "a", filter=editable_focus)
    def _expand_all(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            selectors[uid].toggle_expand_all()
        event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=None)

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", filter=~new_input_focus, eager=True)
    def _back(event) -> None:
        dispatch_tui_back(event, close=close)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bind_case_insensitive_key(bindings, "q", filter=~new_input_focus, eager=True)
    def _close(event) -> None:
        close(event)

    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
