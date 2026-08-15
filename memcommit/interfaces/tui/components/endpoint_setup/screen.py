"""Shared mode and Context-role setup screen for rebuilt TUI operations."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition, has_focus
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
from memcommit.interfaces.tui.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupSpec,
    EndpointSetupValue,
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
from memcommit.selection import FlatSelectionState, SelectionOption
from memcommit.selection.tui import render_vertical_choice_rows


DraftValidator = Callable[[EndpointSetupDraft], str | None]


def run_endpoint_setup(
    spec: EndpointSetupSpec,
    *,
    validate_draft: DraftValidator | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> EndpointSetupDraft | None:
    """Collect an operation shape without opening content or changing state."""

    if not isinstance(spec, EndpointSetupSpec):
        raise TypeError("Endpoint setup requires an EndpointSetupSpec.")
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
    selectors = {
        role.uid: ContextSelectorControl(
            ContextSelectorView(
                names=role.names,
                selected=(role.selected_name,),
                label=(f"{role.label} · FROZEN" if role.fixed else role.label),
                current_context=role.current_context,
                selectable_names=role.selectable_names,
                annotations=role.annotations,
            ),
            height=role.height,
        )
        for role in spec.roles
    }
    reach_states = {
        role.uid: ContextReachState.create(
            include_descendants=role.include_descendants
        )
        for role in spec.roles
        if role.allow_descendants
    }
    bindings = KeyBindings()
    status = {"value": ""}
    role_by_uid = {role.uid: role for role in spec.roles}

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
            title=f"{safe_terminal_text(role.label)} · RANGE",
            is_focused=lambda uid=role.uid: get_app().layout.has_focus(
                reach_controls[uid]
            ),
            height=Dimension.exact(3),
        )

    def make_draft() -> EndpointSetupDraft:
        selected_mode = mode_state.selected_uid
        if selected_mode is None:
            raise ValueError("Choose one operation shape.")
        return EndpointSetupDraft(
            mode_uid=selected_mode,
            values=tuple(
                EndpointSetupValue(
                    role.uid,
                    selectors[role.uid].selection.selected_name,
                    include_descendants=(
                        reach_states[role.uid].include_descendants
                        if role.uid in reach_states
                        else False
                    ),
                )
                for role in spec.roles
            ),
        )

    def render_action() -> list[tuple[str, str]]:
        draft = make_draft()
        focused = get_app().layout.has_focus(action_control)
        fragments: list[tuple[str, str]] = [
            ("class:report-label", "SETUP · NOT RUN\n"),
            ("class:report-neutral", f"MODE · {safe_terminal_text(draft.mode_uid)}\n"),
        ]
        for value in draft.values:
            range_suffix = (
                " · INCLUDE DESCENDANTS"
                if value.include_descendants
                else " · THIS CONTEXT ONLY"
            )
            if not role_by_uid[value.role_uid].allow_descendants:
                range_suffix = ""
            fragments.append(
                (
                    "class:report-neutral",
                    f"{safe_terminal_text(value.role_uid)} · "
                    f"{safe_terminal_text(value.context_name)}"
                    f"{range_suffix}\n",
                )
            )
        fragments.extend(
            [
                ("", "\n"),
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
        title="TO DO · SETUP ONLY",
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

    editable_roles = tuple(role for role in spec.roles if not role.fixed)
    editable_controls = tuple(selectors[role.uid].control for role in editable_roles)

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if get_app().layout.has_focus(mode_control):
            return " ←/→ or ↑/↓ choose shape · Tab endpoint · Esc cancel"
        if get_app().layout.has_focus(action_control):
            return " Enter run selected setup · ↑ endpoint · Esc cancel"
        if any(
            get_app().layout.has_focus(control)
            for control in reach_controls.values()
        ):
            return " ←/→ choose this Context only or include descendants · Tab next · Esc cancel"
        return " ↑/↓ move/cross · ←/→ tree · Enter/Space select · Tab next · Esc cancel"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    role_regions: list[TuiRegion] = []
    for role in spec.roles:
        role_regions.append(TuiRegion(selectors[role.uid].frame))
        if role.uid in reach_frames:
            role_regions.append(TuiRegion(reach_frames[role.uid]))
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(mode_frame),
        *role_regions,
        TuiRegion(action_frame),
        TuiRegion(footer),
    )
    initial_focus = editable_controls[0] if editable_controls else mode_control
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
        status["value"] = ""
        return "MOVED" if changed else "BOUNDARY"

    def choose_mode(_event) -> SurfaceActionResult:
        mode_state.select_cursor(toggle=False)
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
            selectors[role_uid].choose_cursor()
        except ValueError as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
        return "HANDLED"

    def finish(event) -> SurfaceActionResult:
        try:
            draft = make_draft()
            message = validate_draft(draft) if validate_draft is not None else None
            if message:
                raise ValueError(message)
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(result=draft)
        return "HANDLED"

    surfaces_in_order = [
        FocusSurface(
            "MODE",
            mode_control,
            move_vertical=move_mode,
            activate=choose_mode,
        )
    ]
    editable_role_uids = {role.uid for role in editable_roles}
    for role in spec.roles:
        if role.uid in editable_role_uids:
            surfaces_in_order.append(
                FocusSurface(
                    f"ROLE:{role.uid}",
                    selectors[role.uid].control,
                    move_vertical=lambda _event, delta, uid=role.uid: move_role(
                        uid, delta
                    ),
                    activate=lambda _event, uid=role.uid: choose_role(uid),
                    on_vertical_enter=lambda delta, uid=role.uid: enter_role(
                        uid, delta
                    ),
                )
            )
        if role.uid in reach_controls:
            surfaces_in_order.append(
                FocusSurface(
                    f"RANGE:{role.uid}",
                    reach_controls[role.uid],
                    move_vertical=lambda _event, _delta: "BOUNDARY",
                )
            )
    surfaces_in_order.append(
        FocusSurface(
            "CONTINUE",
            action_control,
            move_vertical=lambda _event, _delta: "BOUNDARY",
            activate=finish,
        )
    )
    surfaces = SurfaceFocusController(tuple(surfaces_in_order))
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
            get_app().layout.has_focus(control)
            for control in reach_controls.values()
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
            reach_states[uid].move(delta)
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

    @bind_case_insensitive_key(bindings, "a", filter=editable_focus)
    def _expand_all(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            selectors[uid].toggle_expand_all()
        event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=None)

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
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
