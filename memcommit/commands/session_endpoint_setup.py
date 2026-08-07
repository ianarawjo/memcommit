"""Role-based Context endpoint setup shared by durable operation launchers."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.commands.context_picker import ContextTreeState, build_context_tree
from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    bind_focused_frame_style,
    display_escape_text,
    focused_control_style,
    focus_in_order,
)
from memcommit.store import validate_context_name


@dataclass(frozen=True)
class EndpointModeSpec:
    uid: str
    label: str
    active_roles: tuple[str, ...]
    role_titles: Mapping[str, str]
    description: str = ""
    descendant_roles: frozenset[str] = frozenset()


@dataclass(frozen=True)
class EndpointRoleSpec:
    uid: str
    selectable_names: frozenset[str]
    initial_name: str
    allow_new: bool = False
    new_label: str = "NEW CONTEXT"
    initial_new_name: str = ""
    prefer_new: bool = False
    allow_descendants: bool = False


@dataclass(frozen=True)
class EndpointValue:
    role_uid: str
    context_name: str
    create: bool = False
    include_descendants: bool = False


@dataclass(frozen=True)
class EndpointSetupDraft:
    mode_uid: str
    values: tuple[EndpointValue, ...]

    def value(self, role_uid: str) -> EndpointValue:
        return next(value for value in self.values if value.role_uid == role_uid)


DraftValidator = Callable[[EndpointSetupDraft], str | None]


def _endpoint_row_styles(
    *,
    cursor: bool,
    chosen: bool,
    tree_focused: bool,
) -> tuple[str, str]:
    """Separate a retained endpoint choice from the live tree cursor."""

    cursor_focused = cursor and tree_focused
    cursor_style = (
        "class:memcommit.table.selected" if cursor_focused else ""
    )
    value_style = (
        focused_control_style(
            focused=cursor_focused,
            selected=True,
        )
        if chosen
        else cursor_style
    )
    return cursor_style, value_style


def _new_context_label_style(*, focused: bool) -> str:
    """Highlight the create-new action only while its editor owns focus."""

    # ``create`` remains the semantic endpoint choice after Tab moves on, but
    # this label is an action affordance rather than a retained-choice badge.
    # Keeping its blue surface would falsely imply that it still owns input.
    return focused_control_style(focused=focused, selected=focused)


def _new_context_action_hint(*, focused: bool) -> str:
    """Describe the key that is safe in the create-new control's mode."""

    return " · ENTER CONFIRM" if focused else ""


def _confirmed_new_context_row(
    name: str,
    *,
    anchor: bool,
) -> list[tuple[str, str]]:
    """Render one confirmed, process-local endpoint choice in its selector."""

    fragments: list[tuple[str, str]] = []
    if anchor:
        fragments.append(("[SetCursorPosition]", ""))
    fragments.extend(
        [
            ("class:memcommit.choice.active", "    + "),
            (
                "class:memcommit.choice.active",
                f"{display_escape_text(name)}  NEW · NOT CREATED",
            ),
        ]
    )
    return fragments


def choose_session_endpoints(
    catalog_names: Sequence[str],
    *,
    title: str,
    modes: Sequence[EndpointModeSpec],
    roles: Sequence[EndpointRoleSpec],
    initial_mode_uid: str,
    annotations: Mapping[str, str] | None = None,
    validate_draft: DraftValidator | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> EndpointSetupDraft | None:
    """Collect one process-local role draft without loading operation state."""
    catalog = tuple(catalog_names)
    mode_specs = tuple(modes)
    role_specs = tuple(roles)
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(f"Interactive {title} setup requires a TTY.")
    if not catalog or len(set(catalog)) != len(catalog):
        raise ValueError("Endpoint setup requires a distinct Context catalog.")
    if any(not isinstance(name, str) or not name for name in catalog):
        raise ValueError("Endpoint setup received an invalid Context name.")
    mode_by_uid = {mode.uid: mode for mode in mode_specs}
    role_by_uid = {role.uid: role for role in role_specs}
    if (
        not mode_specs
        or len(mode_by_uid) != len(mode_specs)
        or initial_mode_uid not in mode_by_uid
        or not role_specs
        or len(role_by_uid) != len(role_specs)
    ):
        raise ValueError("Endpoint setup received invalid mode or role specs.")
    catalog_set = frozenset(catalog)
    for mode in mode_specs:
        if not mode.uid or not mode.label or not mode.active_roles:
            raise ValueError("Endpoint setup modes must be named and nonempty.")
        if set(mode.active_roles) != set(mode.role_titles):
            raise ValueError("Endpoint setup mode titles must cover active roles.")
        if not set(mode.active_roles) <= set(role_by_uid):
            raise ValueError("Endpoint setup mode references an unknown role.")
        if (
            not mode.descendant_roles <= set(mode.active_roles)
            or any(
                not role_by_uid[uid].allow_descendants
                for uid in mode.descendant_roles
            )
        ):
            raise ValueError(
                "Endpoint setup mode enables an unavailable descendant scope."
            )
    for role in role_specs:
        if (
            not role.uid
            or (not role.selectable_names and not role.allow_new)
            or not role.selectable_names <= catalog_set
            or role.initial_name not in catalog_set
        ):
            raise ValueError("Endpoint setup received an invalid role spec.")
    labels = dict(annotations or {})
    if set(labels) - catalog_set:
        raise ValueError("Endpoint setup annotations are outside the catalog.")

    tree = build_context_tree(catalog, materialized_names=catalog_set)
    states = {
        role.uid: ContextTreeState.create(tree, selected=role.initial_name)
        for role in role_specs
    }
    selected = {role.uid: role.initial_name for role in role_specs}
    create = {role.uid: role.prefer_new for role in role_specs}
    confirmed_new_names = {
        role.uid: role.initial_new_name.strip() if role.prefer_new else ""
        for role in role_specs
    }
    mode_state = HorizontalChoiceState(
        tuple(
            HorizontalChoiceOption(mode.uid, mode.label, mode.description)
            for mode in mode_specs
        ),
        selected_uid=initial_mode_uid,
    )
    status = {"value": ""}
    bindings = KeyBindings()
    controls: dict[str, FormattedTextControl] = {}
    descendant_controls: dict[str, FormattedTextControl] = {}
    include_descendants = {role.uid: False for role in role_specs}
    frames: dict[str, Frame] = {}
    new_inputs: dict[str, TextArea] = {}
    app_ref: dict[str, Application[EndpointSetupDraft | None]] = {}

    def active_mode() -> EndpointModeSpec:
        return mode_by_uid[mode_state.selected_uid]

    def role_is_active(uid: str) -> bool:
        return uid in active_mode().active_roles

    def role_title(uid: str) -> str:
        return active_mode().role_titles.get(uid, uid)

    def role_descendants_active(uid: str) -> bool:
        return uid in active_mode().descendant_roles

    def render_role(uid: str):
        fragments: list[tuple[str, str]] = []
        state = states[uid]
        role = role_by_uid[uid]
        tree_focused = (
            app_ref.get("app") is not None
            and app_ref["app"].layout.has_focus(controls[uid])
        )
        for index, row in enumerate(state.visible_rows()):
            cursor = row.name == state.selected_name
            confirmed_name = confirmed_new_names[uid]
            if cursor and (tree_focused or not (create[uid] and confirmed_name)):
                fragments.append(("[SetCursorPosition]", ""))
            available = row.name in role.selectable_names
            chosen = not create[uid] and selected[uid] == row.name
            pointer = "›" if cursor else " "
            branch = "▾" if row.expanded else "▸" if row.has_children else "·"
            annotation = labels.get(row.name, "")
            if not available:
                annotation = annotation or "UNAVAILABLE"
            suffix = f"  {display_escape_text(annotation)}" if annotation else ""
            cursor_style, value_style = _endpoint_row_styles(
                cursor=cursor,
                chosen=chosen,
                tree_focused=tree_focused,
            )
            fragments.extend(
                [
                    (
                        cursor_style,
                        f"{pointer}   {'  ' * row.depth}{branch} ",
                    ),
                    (
                        value_style,
                        f"{display_escape_text(row.name)}{suffix}",
                    ),
                ]
            )
            if index < len(state.visible_rows()) - 1:
                fragments.append(("", "\n"))
        if create[uid] and confirmed_name:
            if fragments:
                fragments.append(("", "\n"))
            # Once confirmation advances focus, anchor this retained choice so
            # it stays visible even when a long namespace would otherwise
            # keep the old tree cursor in the viewport.
            fragments.extend(
                _confirmed_new_context_row(
                    confirmed_name,
                    anchor=not tree_focused,
                )
            )
        return fragments

    for role in role_specs:
        control = FormattedTextControl(
            lambda uid=role.uid: render_role(uid),
            focusable=True,
            show_cursor=False,
        )
        controls[role.uid] = control
        tree_window = Window(
            control,
            wrap_lines=False,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        body_parts: list[object] = [tree_window]
        if role.allow_descendants:
            descendant_control = FormattedTextControl(
                lambda uid=role.uid: [
                    ("[SetCursorPosition]", ""),
                    (
                        focused_control_style(
                            focused=(
                                app_ref.get("app") is not None
                                and app_ref["app"].layout.has_focus(
                                    descendant_controls[uid]
                                )
                            ),
                            selected=include_descendants[uid],
                        ),
                        "  ["
                        + ("✓" if include_descendants[uid] else " ")
                        + "] INCLUDE ALL DESCENDANT CONTEXTS "
                        "(OWNED OR GRANTED)",
                    ),
                ],
                focusable=True,
                show_cursor=False,
            )
            descendant_controls[role.uid] = descendant_control
            body_parts.append(
                ConditionalContainer(
                    HSplit(
                        [
                            Window(height=1, char="─"),
                            Window(
                                descendant_control,
                                height=1,
                                dont_extend_height=True,
                            ),
                        ]
                    ),
                    filter=Condition(
                        lambda uid=role.uid: role_descendants_active(uid)
                    ),
                )
            )
        if role.allow_new:
            editor = TextArea(
                text=role.initial_new_name,
                multiline=False,
                prompt="› ",
                height=1,
                name=f"endpoint-{role.uid.casefold()}-new-name",
            )
            new_inputs[role.uid] = editor
            body_parts.extend(
                [
                    Window(height=1, char="─"),
                    Window(
                        FormattedTextControl(
                            lambda uid=role.uid: [
                                ("", "  NEW · "),
                                (
                                    _new_context_label_style(
                                        focused=(
                                            app_ref.get("app") is not None
                                            and app_ref["app"].layout.has_focus(
                                                new_inputs[uid]
                                            )
                                        )
                                    ),
                                    "[ "
                                    f"{display_escape_text(role_by_uid[uid].new_label)}"
                                    " ]",
                                ),
                                (
                                    "",
                                    _new_context_action_hint(
                                        focused=(
                                            app_ref.get("app") is not None
                                            and app_ref["app"].layout.has_focus(
                                                new_inputs[uid]
                                            )
                                        )
                                    ),
                                ),
                            ]
                        ),
                        height=1,
                    ),
                    editor,
                ]
            )
        body: object = HSplit(body_parts) if len(body_parts) > 1 else tree_window
        frame = Frame(body, title=lambda uid=role.uid: role_title(uid))
        frames[role.uid] = frame
        bind_focused_frame_style(
            frame,
            is_focused=lambda uid=role.uid: (
                app_ref.get("app") is not None
                and (
                    app_ref["app"].layout.has_focus(controls[uid])
                    or (
                        uid in descendant_controls
                        and role_descendants_active(uid)
                        and app_ref["app"].layout.has_focus(
                            descendant_controls[uid]
                        )
                    )
                    or (
                        uid in new_inputs
                        and app_ref["app"].layout.has_focus(new_inputs[uid])
                    )
                )
            ),
        )

    mode_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            mode_state,
            title="MODE",
            focused=app_ref.get("app") is not None
            and app_ref["app"].layout.has_focus(mode_control),
            show_description=True,
            boxed=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    mode_frame = Frame(
        Window(mode_control, height=5, dont_extend_height=True),
        title="OPERATION SHAPE",
    )
    bind_focused_frame_style(
        mode_frame,
        is_focused=lambda: app_ref.get("app") is not None
        and app_ref["app"].layout.has_focus(mode_control),
    )

    apply_control = FormattedTextControl(
        lambda: [
            ("[SetCursorPosition]", ""),
            (
                focused_control_style(
                    focused=(
                        app_ref.get("app") is not None
                        and app_ref["app"].layout.has_focus(apply_control)
                    ),
                ),
                "[ PRESS ENTER TO APPLY ]",
            ),
        ],
        focusable=True,
        show_cursor=False,
    )
    apply_window = Window(
        apply_control,
        height=1,
        align=WindowAlign.LEFT,
        dont_extend_height=True,
    )
    apply_frame = Frame(apply_window, title="APPLY")
    bind_focused_frame_style(
        apply_frame,
        is_focused=lambda: app_ref.get("app") is not None
        and app_ref["app"].layout.has_focus(apply_control),
    )

    def active_focusables():
        values: list[object] = []
        if len(mode_specs) > 1:
            values.append(mode_control)
        for uid in active_mode().active_roles:
            values.append(controls[uid])
            if uid in descendant_controls and role_descendants_active(uid):
                values.append(descendant_controls[uid])
        values.append(apply_control)
        return values

    def vertical_focusables():
        """Return visible controls in their top-to-bottom screen order."""

        values: list[object] = []
        if len(mode_specs) > 1:
            values.append(mode_control)
        for uid in active_mode().active_roles:
            values.append(controls[uid])
            if uid in descendant_controls and role_descendants_active(uid):
                values.append(descendant_controls[uid])
            if uid in new_inputs:
                values.append(new_inputs[uid])
        values.append(apply_control)
        return values

    def focus_vertical_neighbor(event, delta: int) -> bool:
        """Cross a visible surface boundary without wrapping the screen."""

        focusables = vertical_focusables()
        index = next(
            (
                i
                for i, control in enumerate(focusables)
                if event.app.layout.has_focus(control)
            ),
            -1,
        )
        next_index = index + delta
        if index < 0 or not 0 <= next_index < len(focusables):
            return False
        target = focusables[next_index]
        # A Context tree is one visual run of rows in the larger screen. Enter
        # it at the adjacent edge so Up/Down never skips a visible Context.
        target_uid = next(
            (uid for uid, control in controls.items() if control is target),
            None,
        )
        if target_uid is not None:
            rows = states[target_uid].visible_rows()
            states[target_uid].selected_name = rows[0 if delta > 0 else -1].name
        event.app.layout.focus(target)
        return True

    def focused_role_uid() -> str | None:
        app = app_ref["app"]
        for uid in active_mode().active_roles:
            if app.layout.has_focus(controls[uid]) or (
                uid in descendant_controls
                and role_descendants_active(uid)
                and app.layout.has_focus(descendant_controls[uid])
            ) or (
                uid in new_inputs and app.layout.has_focus(new_inputs[uid])
            ):
                return uid
        return None

    def make_draft() -> EndpointSetupDraft:
        values: list[EndpointValue] = []
        for uid in active_mode().active_roles:
            role = role_by_uid[uid]
            if create[uid]:
                if not role.allow_new:
                    raise ValueError(f"{role_title(uid)} cannot create a Context.")
                name = confirmed_new_names[uid]
                if not name:
                    raise ValueError(
                        f"{role_title(uid)} new Context name must be confirmed "
                        "with Enter."
                    )
                validate_context_name(name)
                if name in catalog_set:
                    raise ValueError(
                        f"{role_title(uid)} new Context already exists. Select it instead."
                    )
                values.append(EndpointValue(uid, name, create=True))
            else:
                name = selected[uid]
                if name not in role.selectable_names:
                    raise ValueError(f"{role_title(uid)} is unavailable.")
                values.append(
                    EndpointValue(
                        uid,
                        name,
                        include_descendants=(
                            include_descendants[uid]
                            if role_descendants_active(uid)
                            else False
                        ),
                    )
                )
        return EndpointSetupDraft(active_mode().uid, tuple(values))

    def finish(event) -> None:
        try:
            draft = make_draft()
            message = validate_draft(draft) if validate_draft is not None else None
            if message:
                raise ValueError(message)
        except ValueError as error:
            status["value"] = str(error)
            event.app.invalidate()
            return
        event.app.exit(result=draft)

    tree_focus = Condition(
        lambda: any(app_ref["app"].layout.has_focus(control) for control in controls.values())
    )
    descendant_focus = Condition(
        lambda: any(
            app_ref["app"].layout.has_focus(control)
            for control in descendant_controls.values()
        )
    )
    new_input_focus = Condition(
        lambda: any(
            app_ref["app"].layout.has_focus(editor)
            for editor in new_inputs.values()
        )
    )

    @bindings.add("down", filter=tree_focus, eager=True)
    def _down(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            state = states[uid]
            before = state.selected_name
            state.move(1)
            if state.selected_name == before:
                focus_vertical_neighbor(event, 1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("up", filter=tree_focus, eager=True)
    def _up(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            state = states[uid]
            before = state.selected_name
            state.move(-1)
            if state.selected_name == before:
                focus_vertical_neighbor(event, -1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("down", filter=descendant_focus, eager=True)
    def _down_from_descendants(event) -> None:
        focus_vertical_neighbor(event, 1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("up", filter=descendant_focus, eager=True)
    def _up_from_descendants(event) -> None:
        focus_vertical_neighbor(event, -1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("down", filter=new_input_focus, eager=True)
    def _down_from_new_input(event) -> None:
        focus_vertical_neighbor(event, 1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("up", filter=new_input_focus, eager=True)
    def _up_from_new_input(event) -> None:
        focus_vertical_neighbor(event, -1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(mode_control), eager=True)
    def _down_from_mode(event) -> None:
        focus_vertical_neighbor(event, 1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(apply_control), eager=True)
    def _up_from_apply(event) -> None:
        focus_vertical_neighbor(event, -1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=tree_focus, eager=True)
    def _expand(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            states[uid].expand_selected()
        event.app.invalidate()

    @bindings.add("left", filter=tree_focus, eager=True)
    def _collapse(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            states[uid].collapse_selected()
        event.app.invalidate()

    @bindings.add("a", filter=tree_focus, eager=True)
    @bindings.add("A", filter=tree_focus, eager=True)
    def _expand_all(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            states[uid].toggle_expand_all()
        event.app.invalidate()

    @bindings.add("enter", filter=tree_focus, eager=True)
    @bindings.add(" ", filter=tree_focus, eager=True)
    def _select_existing(event) -> None:
        uid = focused_role_uid()
        if uid is None:
            return
        name = states[uid].selected_name
        if name not in role_by_uid[uid].selectable_names:
            status["value"] = f"{role_title(uid)} is unavailable."
        else:
            selected[uid] = name
            create[uid] = False
            status["value"] = ""
        event.app.invalidate()

    @bindings.add("enter", filter=descendant_focus, eager=True)
    @bindings.add(" ", filter=descendant_focus, eager=True)
    def _toggle_descendants(event) -> None:
        uid = focused_role_uid()
        if uid is not None and uid in descendant_controls:
            include_descendants[uid] = not include_descendants[uid]
            status["value"] = ""
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(mode_control), eager=True)
    def _previous_mode(event) -> None:
        mode_state.move(-1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(mode_control), eager=True)
    def _next_mode(event) -> None:
        mode_state.move(1)
        status["value"] = ""
        event.app.invalidate()

    for uid, editor in new_inputs.items():
        editor_filter = has_focus(editor)

        @bindings.add("enter", filter=editor_filter, eager=True)
        def _accept_new(event, role_uid=uid) -> None:
            try:
                name = new_inputs[role_uid].text.strip()
                validate_context_name(name)
                if name in catalog_set:
                    raise ValueError("That Context already exists; select its tree row.")
            except ValueError as error:
                status["value"] = str(error)
                event.app.invalidate()
                return
            confirmed_new_names[role_uid] = name
            create[role_uid] = True
            status["value"] = ""
            focus_vertical_neighbor(event, 1)
            event.app.invalidate()

    @bindings.add("tab", filter=new_input_focus, eager=True)
    def _next_focus_from_new_input(event) -> None:
        focus_vertical_neighbor(event, 1)
        event.app.invalidate()

    @bindings.add("s-tab", filter=new_input_focus, eager=True)
    def _previous_focus_from_new_input(event) -> None:
        focus_vertical_neighbor(event, -1)
        event.app.invalidate()

    @bindings.add("tab", filter=~new_input_focus)
    def _next_focus(event) -> None:
        focusables = active_focusables()
        focus_in_order(event.app, focusables, 1, wrap=True)
        event.app.invalidate()

    @bindings.add("s-tab", filter=~new_input_focus)
    def _previous_focus(event) -> None:
        focusables = active_focusables()
        focus_in_order(event.app, focusables, -1, wrap=True)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(apply_control), eager=True)
    @bindings.add(" ", filter=has_focus(apply_control), eager=True)
    def _apply(event) -> None:
        finish(event)

    @bindings.add("escape", filter=new_input_focus, eager=True)
    def _leave_new_editor(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            event.app.layout.focus(controls[uid])
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("escape", filter=~new_input_focus, eager=True)
    @bindings.add("q", filter=~new_input_focus, eager=True)
    @bindings.add("Q", filter=~new_input_focus, eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def render_header() -> str:
        return f" {display_escape_text(title)} · {active_mode().label}"

    def render_footer() -> str:
        uid = focused_role_uid()
        if (
            uid is not None
            and uid in new_inputs
            and app_ref["app"].layout.has_focus(new_inputs[uid])
        ):
            guidance = "Enter confirm name · Esc back · Tab pane"
            if status["value"]:
                return f" {display_escape_text(status['value'])} · {guidance}"
            return f" NEW CONTEXT NAME: {guidance}"
        if status["value"]:
            return f" {display_escape_text(status['value'])}"
        if app_ref["app"].layout.has_focus(apply_control):
            return " APPLY: Enter/Space apply · ↑ previous · Tab pane · Q cancel"
        if app_ref["app"].layout.has_focus(mode_control):
            return " MODE: ←/→ choose · ↓ endpoints · Tab endpoints · Q cancel"
        if uid is not None and uid in descendant_controls and app_ref[
            "app"
        ].layout.has_focus(descendant_controls[uid]):
            return (
                " SCOPE: Enter/Space include all descendants · "
                "↑/↓ move · Tab pane · Q cancel"
            )
        return " ↑/↓ move · ←/→ tree · Enter/Space choose · Tab pane · Q cancel"

    children: list[object] = []
    if len(mode_specs) > 1:
        children.append(mode_frame)
    children.extend(
        ConditionalContainer(
            frames[role.uid],
            filter=Condition(lambda uid=role.uid: role_is_active(uid)),
        )
        for role in role_specs
    )
    root = HSplit(
        [
            Window(FormattedTextControl(render_header), height=1),
            Window(height=1, char="─"),
            *children,
            apply_frame,
            Window(FormattedTextControl(render_footer), height=1),
        ]
    )
    initial_focus = mode_control if len(mode_specs) > 1 else controls[active_mode().active_roles[0]]
    app: Application[EndpointSetupDraft | None] = Application(
        layout=Layout(root, focused_element=initial_focus),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=MEMCOMMIT_TUI_STYLE,
    )
    app_ref["app"] = app
    return app.run()
