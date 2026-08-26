"""Role-based Context endpoint setup shared by durable operation launchers."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from prompt_toolkit.application import Application, get_app
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
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.context_targeting.tui.reach import (
    ContextReachState,
    render_context_reach,
)
from memcommit.context_targeting.naming import validate_portable_context_name
from memcommit.context_targeting.tui.range_selection import (
    project_checked_context_names,
)
from memcommit.context_targeting.tui.name_draft import (
    ContextNameDraftState,
    infer_context_parent,
)
from memcommit.context_targeting.tui.rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.context_targeting.tui.selection import ContextSelectionState
from memcommit.context_targeting.tui.tree import ContextTreeState, build_context_tree
from memcommit.context_targeting.tui.memory_selection import (
    DirectMemorySelectionState,
)
from memcommit.selection.tui import tree_choice_marker, tree_choice_styles
from memcommit.context_targeting.tui.picker import (
    CONTEXT_PICKER_STYLE,
    ContextMemoryPreviewController,
    ContextMemoryRow,
    memory_visibility_key_hint,
)
from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.commands.tui_primitives import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    focused_control_style,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    bind_tui_interrupt,
)
from memcommit.interfaces.tui.components.frame import (
    bind_focused_frame_style,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceFocusController,
    focus_in_order,
)
from memcommit.source_projection.model import SourceDisplayFacts, SourceState
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceDisplayValue,
    SourceTokenRole,
    combine_source_display_tokens,
    normalize_source_display_tokens,
)


@dataclass(frozen=True)
class EndpointModeSpec:
    uid: str
    label: str
    active_roles: tuple[str, ...]
    role_titles: Mapping[str, str]
    description: str = ""
    descendant_roles: frozenset[str] = frozenset()
    memory_focus_roles: frozenset[str] = frozenset()


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
    selectable_annotation: str = ""
    new_name_suggester: Callable[[Mapping[str, str]], str] | None = None
    new_parent_locator: bool = False
    allow_memory_focus: bool = False


@dataclass(frozen=True)
class EndpointValue:
    role_uid: str
    context_name: str
    create: bool = False
    include_descendants: bool = False
    memory_uid: str | None = None


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

    return tree_choice_styles(
        cursor=cursor,
        selected=chosen,
        focused=tree_focused,
    )


def _endpoint_checked_names(
    tree: ContextTreeState,
    selection: ContextSelectionState,
    reach: ContextReachState,
    *,
    descendants_active: bool,
    selectable_names: frozenset[str],
    existing_selected: bool,
) -> frozenset[str]:
    """Return the effective existing-Context rows for one endpoint role."""

    if not existing_selected:
        return frozenset()
    return frozenset(
        project_checked_context_names(
            tree.tree,
            selection.selected_names,
            include_descendants=(
                descendants_active and reach.include_descendants
            ),
            selectable_names=selectable_names,
        )
    )


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
                f"{display_escape_text(name)}  NEW · CREATE ON START",
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
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
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
        if not mode.descendant_roles <= set(mode.active_roles) or any(
            not role_by_uid[uid].allow_descendants for uid in mode.descendant_roles
        ):
            raise ValueError(
                "Endpoint setup mode enables an unavailable descendant scope."
            )
        if not mode.memory_focus_roles <= set(mode.active_roles) or any(
            not role_by_uid[uid].allow_memory_focus
            for uid in mode.memory_focus_roles
        ):
            raise ValueError(
                "Endpoint setup mode enables unavailable Memory focus."
            )
    for role in role_specs:
        if (
            not role.uid
            or (not role.selectable_names and not role.allow_new)
            or not role.selectable_names <= catalog_set
            or role.initial_name not in catalog_set
        ):
            raise ValueError("Endpoint setup received an invalid role spec.")
        if not isinstance(role.selectable_annotation, str) or any(
            character in role.selectable_annotation for character in "\r\n"
        ):
            raise ValueError("Endpoint role annotation must be one-line text.")
        if role.new_name_suggester is not None and (
            not role.allow_new or not callable(role.new_name_suggester)
        ):
            raise ValueError(
                "Endpoint new-name suggestion requires a creatable role callback."
            )
        if role.new_parent_locator and (
            not role.allow_new
            or not role.prefer_new
            or not role.initial_new_name.strip()
            or role.allow_descendants
            or role.selectable_annotation
        ):
            raise ValueError(
                "Endpoint parent location requires a new-only role without "
                "descendant or row-availability semantics."
            )
    labels = dict(annotations or {})
    if set(labels) - catalog_set:
        raise ValueError("Endpoint setup annotations are outside the catalog.")
    try:
        for annotation in labels.values():
            normalize_source_display_tokens(annotation)
    except (TypeError, ValueError) as error:
        raise ValueError("Endpoint setup received an invalid annotation.") from error

    tree = build_context_tree(catalog, materialized_names=catalog_set)
    states = {
        role.uid: ContextTreeState.create(tree, selected=role.initial_name)
        for role in role_specs
    }
    selections = {
        role.uid: ContextSelectionState.create(
            catalog,
            selected=(role.initial_name,),
            mode="SINGLE",
        )
        for role in role_specs
    }
    memory_previews = {
        role.uid: ContextMemoryPreviewController(states[role.uid], memory_loader)
        for role in role_specs
        if memory_loader is not None
    }
    memory_selections = {
        role.uid: DirectMemorySelectionState()
        for role in role_specs
        if role.allow_memory_focus
    }
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
    descendant_scope = {
        role.uid: ContextReachState.create(include_descendants=False)
        for role in role_specs
    }
    frames: dict[str, Frame] = {}
    new_inputs: dict[str, TextArea] = {}
    new_name_fields: dict[str, ExactNameInputControl] = {}
    suggested_new_names = {
        role.uid: role.initial_new_name for role in role_specs if role.allow_new
    }
    edited_new_names = {role.uid: False for role in role_specs if role.allow_new}
    new_name_drafts = {
        role.uid: ContextNameDraftState(
            exact_name=role.initial_new_name,
            parent_name=role.initial_name,
        )
        for role in role_specs
        if role.new_parent_locator
    }
    updating_new_names: set[str] = set()
    app_ref: dict[str, Application[EndpointSetupDraft | None]] = {}

    def active_mode() -> EndpointModeSpec:
        return mode_by_uid[mode_state.selected_uid]

    def role_is_active(uid: str) -> bool:
        return uid in active_mode().active_roles

    def role_title(uid: str) -> str:
        return active_mode().role_titles.get(uid, uid)

    def role_descendants_active(uid: str) -> bool:
        return uid in active_mode().descendant_roles

    def role_memory_focus_active(uid: str) -> bool:
        return uid in active_mode().memory_focus_roles

    def clear_inactive_memory_selections() -> None:
        for uid, selection in memory_selections.items():
            if not role_memory_focus_active(uid):
                selection.clear()

    def clear_hidden_memory_selection(uid: str) -> bool:
        """Never retain an executable Memory UID after its row is hidden."""

        selection = memory_selections.get(uid)
        preview = memory_previews.get(uid)
        if selection is None or selection.selected is None or preview is None:
            return False
        if selection.selected.context_name in preview.visible_memory_contexts():
            return False
        cleared = selection.clear()
        if cleared:
            status["value"] = (
                "Focused Memory selection cleared because its preview was hidden."
            )
        return cleared

    def render_role(uid: str):
        state = states[uid]
        role = role_by_uid[uid]
        preview = memory_previews.get(uid)
        memory_focused = preview is not None and preview.memory_focused
        memory_focus_active = role_memory_focus_active(uid)
        selected_memory = (
            memory_selections[uid].selected
            if uid in memory_selections and memory_focus_active
            else None
        )
        tree_focused = app_ref.get("app") is not None and app_ref[
            "app"
        ].layout.has_focus(controls[uid])
        wrap_width = max(1, get_app().output.get_size().columns - 1)
        checked_names = _endpoint_checked_names(
            state,
            selections[uid],
            descendant_scope[uid],
            descendants_active=role_descendants_active(uid),
            selectable_names=role.selectable_names,
            existing_selected=(role.new_parent_locator or not create[uid]),
        )

        def decorate(row, cursor: bool) -> ContextTreeRowDecoration:
            confirmed_name = confirmed_new_names[uid]
            available = row.name in role.selectable_names
            chosen = row.name in checked_names
            annotation: SourceDisplayValue | None = labels.get(row.name)
            if not available:
                annotation = combine_source_display_tokens(
                    annotation,
                    SourceDisplayFacts(states=(SourceState.UNAVAILABLE,)),
                )
            elif role.selectable_annotation:
                annotation = combine_source_display_tokens(
                    annotation,
                    SourceDisplayToken(
                        role.selectable_annotation,
                        SourceTokenRole.NOTE,
                    ),
                )
            cursor_style, value_style = _endpoint_row_styles(
                cursor=cursor and not memory_focused,
                chosen=chosen,
                tree_focused=tree_focused,
            )
            return ContextTreeRowDecoration(
                marker=tree_choice_marker(selected=chosen, available=available),
                annotation=annotation,
                value_suffix="/" if role.new_parent_locator else "",
                cursor_style=cursor_style,
                value_style=value_style,
                branch=preview.branch_for(row) if preview is not None else None,
                nested_fragments=(
                    preview.render_nested(
                        row,
                        wrap_width=wrap_width,
                        selectable_memories=memory_focus_active,
                        selected_memory=selected_memory,
                    )
                    if preview is not None
                    else ()
                ),
                anchor_cursor=(
                    not memory_focused
                    and (
                        tree_focused
                        or role.new_parent_locator
                        or not (create[uid] and confirmed_name)
                    )
                ),
            )

        fragments = render_context_tree_rows(state, decorate)
        confirmed_name = confirmed_new_names[uid]
        if create[uid] and confirmed_name and not role.new_parent_locator:
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

            def render_descendant_scope(uid=role.uid):
                fragments: list[tuple[str, str]] = [("[SetCursorPosition]", "")]
                fragments.extend(
                    render_context_reach(
                        descendant_scope[uid],
                        title="RANGE",
                        focused=(
                            app_ref.get("app") is not None
                            and app_ref["app"].layout.has_focus(
                                descendant_controls[uid]
                            )
                        ),
                    )
                )
                return fragments

            descendant_control = FormattedTextControl(
                render_descendant_scope,
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
                    filter=Condition(lambda uid=role.uid: role_descendants_active(uid)),
                )
            )
        if role.allow_new:
            def validate_new_name(candidate: str, *, role_spec=role) -> None:
                validate_portable_context_name(candidate)
                if candidate in catalog_set:
                    if role_spec.new_parent_locator:
                        raise ValueError(
                            "That Context already exists; enter a different exact name."
                        )
                    raise ValueError(
                        "That Context already exists; select its tree row."
                    )

            name_field = ExactNameInputControl.create(
                ExactNameFieldView(
                    value=role.initial_new_name,
                    label=role.new_label,
                    state="CREATE ON START",
                    validate=validate_new_name,
                    value_label="Context name",
                ),
                input_name=f"endpoint-{role.uid.casefold()}-new-name",
            )
            new_name_fields[role.uid] = name_field
            editor = name_field.input
            new_inputs[role.uid] = editor

            def mark_new_name_edited(_buffer, *, role_uid=role.uid) -> None:
                if role_uid not in updating_new_names:
                    # Once the person changes the draft, later endpoint choices
                    # must not silently replace it with another suggestion.
                    edited_new_names[role_uid] = True
                    if role_uid in new_name_drafts:
                        new_name_drafts[role_uid].record_direct_edit(
                            new_name_fields[role_uid].text
                        )

            editor.buffer.on_text_changed += mark_new_name_edited
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
                                    (
                                        " · ENTER CONTINUE"
                                        if role_by_uid[uid].new_parent_locator
                                        and app_ref.get("app") is not None
                                        and app_ref["app"].layout.has_focus(
                                            new_inputs[uid]
                                        )
                                        else _new_context_action_hint(
                                            focused=(
                                                app_ref.get("app") is not None
                                                and app_ref["app"].layout.has_focus(
                                                    new_inputs[uid]
                                                )
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
                        and app_ref["app"].layout.has_focus(descendant_controls[uid])
                    )
                    or (
                        uid in new_inputs
                        and app_ref["app"].layout.has_focus(new_inputs[uid])
                    )
                )
            ),
        )

    def refresh_new_name_suggestions() -> None:
        selected_names = {
            role.uid: selections[role.uid].selected_name for role in role_specs
        }
        for role in role_specs:
            if role.new_name_suggester is None:
                continue
            candidate = role.new_name_suggester(selected_names)
            validate_portable_context_name(candidate)
            if candidate in catalog_set:
                raise ValueError(
                    f"Suggested {role_title(role.uid)} Context already exists."
                )
            previous = suggested_new_names[role.uid]
            suggested_new_names[role.uid] = candidate
            if role.new_parent_locator:
                draft = new_name_drafts[role.uid]
                parent = infer_context_parent(
                    candidate,
                    tuple(
                        name for name in catalog if name in role.selectable_names
                    ),
                    fallback=selections[role.uid].selected_name,
                )
                visible_candidate = draft.inherit_suggestion(
                    candidate,
                    parent_name=parent,
                )
                if draft.edited:
                    continue
                states[role.uid].selected_name = parent
                selections[role.uid].choose(parent)
            else:
                if edited_new_names[role.uid]:
                    continue
                visible_candidate = candidate
            updating_new_names.add(role.uid)
            try:
                new_name_fields[role.uid].set_text(visible_candidate)
            finally:
                updating_new_names.remove(role.uid)
            if confirmed_new_names[role.uid] == previous:
                confirmed_new_names[role.uid] = visible_candidate

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

    def vertical_surfaces() -> tuple[FocusSurface, ...]:
        """Declare visible controls in top-to-bottom screen order."""

        values: list[FocusSurface] = []
        if len(mode_specs) > 1:
            values.append(FocusSurface("mode", mode_control))
        for uid in active_mode().active_roles:

            def enter_tree(delta: int, *, role_uid: str = uid) -> None:
                rows = states[role_uid].visible_rows()
                states[role_uid].selected_name = rows[0 if delta > 0 else -1].name
                preview = memory_previews.get(role_uid)
                if preview is not None:
                    preview.clear_memory_focus()

            values.append(
                FocusSurface(
                    f"role:{uid}",
                    controls[uid],
                    on_vertical_enter=enter_tree,
                )
            )
            if uid in descendant_controls and role_descendants_active(uid):
                values.append(
                    FocusSurface(f"descendants:{uid}", descendant_controls[uid])
                )
            if uid in new_inputs:
                values.append(FocusSurface(f"new:{uid}", new_inputs[uid]))
        values.append(FocusSurface("apply", apply_control))
        return tuple(values)

    vertical_focus = SurfaceFocusController(vertical_surfaces)

    def focus_vertical_neighbor(event, delta: int) -> bool:
        """Cross a visible surface boundary without wrapping the screen."""

        return vertical_focus.focus_relative(
            event.app,
            delta,
            wrap=False,
            vertical_entry=True,
        )

    def focused_role_uid() -> str | None:
        app = app_ref["app"]
        for uid in active_mode().active_roles:
            if (
                app.layout.has_focus(controls[uid])
                or (
                    uid in descendant_controls
                    and role_descendants_active(uid)
                    and app.layout.has_focus(descendant_controls[uid])
                )
                or (uid in new_inputs and app.layout.has_focus(new_inputs[uid]))
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
                name = (
                    new_name_fields[uid].text.strip()
                    if role.new_parent_locator
                    else confirmed_new_names[uid]
                )
                if not name and not role.new_parent_locator:
                    raise ValueError(
                        f"{role_title(uid)} new Context name must be confirmed "
                        "with Enter."
                    )
                if not name:
                    raise ValueError(
                        f"{role_title(uid)} new Context name must be nonempty."
                    )
                validate_portable_context_name(name)
                if name in catalog_set:
                    if role.new_parent_locator:
                        raise ValueError(
                            f"{role_title(uid)} new Context already exists. "
                            "Enter a different exact name."
                        )
                    raise ValueError(
                        f"{role_title(uid)} new Context already exists. Select it instead."
                    )
                values.append(EndpointValue(uid, name, create=True))
            else:
                name = selections[uid].selected_name
                if name not in role.selectable_names:
                    raise ValueError(f"{role_title(uid)} is unavailable.")
                selected_memory = (
                    memory_selections[uid].selected
                    if uid in memory_selections and role_memory_focus_active(uid)
                    else None
                )
                if (
                    selected_memory is not None
                    and selected_memory.context_name != name
                ):
                    raise ValueError(
                        f"{role_title(uid)} Memory selection belongs to another Context."
                    )
                include_descendants = (
                    descendant_scope[uid].include_descendants
                    if role_descendants_active(uid)
                    else False
                )
                if selected_memory is not None and include_descendants:
                    raise ValueError(
                        f"{role_title(uid)} cannot combine Memory focus with descendants."
                    )
                values.append(
                    EndpointValue(
                        uid,
                        name,
                        include_descendants=include_descendants,
                        memory_uid=(
                            selected_memory.memory_uid
                            if selected_memory is not None
                            else None
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
        lambda: any(
            app_ref["app"].layout.has_focus(control) for control in controls.values()
        )
    )
    descendant_focus = Condition(
        lambda: any(
            app_ref["app"].layout.has_focus(control)
            for control in descendant_controls.values()
        )
    )
    new_input_focus = Condition(
        lambda: any(
            app_ref["app"].layout.has_focus(editor) for editor in new_inputs.values()
        )
    )

    @bindings.add("down", filter=tree_focus, eager=True)
    def _down(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            preview = memory_previews.get(uid)
            if preview is not None:
                moved = preview.move(1)
            else:
                state = states[uid]
                before = state.selected_name
                state.move(1)
                moved = state.selected_name != before
            if not moved:
                focus_vertical_neighbor(event, 1)
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("up", filter=tree_focus, eager=True)
    def _up(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            preview = memory_previews.get(uid)
            if preview is not None:
                moved = preview.move(-1)
            else:
                state = states[uid]
                before = state.selected_name
                state.move(-1)
                moved = state.selected_name != before
            if not moved:
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
            preview = memory_previews.get(uid)
            if preview is not None:
                preview.expand_selected()
            else:
                states[uid].expand_selected()
        event.app.invalidate()

    @bindings.add("left", filter=tree_focus, eager=True)
    def _collapse(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            preview = memory_previews.get(uid)
            if preview is not None:
                preview.collapse_selected()
                clear_hidden_memory_selection(uid)
            else:
                states[uid].collapse_selected()
        event.app.invalidate()

    @bindings.add("a", filter=tree_focus, eager=True)
    @bindings.add("A", filter=tree_focus, eager=True)
    def _expand_all(event) -> None:
        uid = focused_role_uid()
        if uid is not None:
            preview = memory_previews.get(uid)
            if preview is not None:
                preview.toggle_expand_all()
                clear_hidden_memory_selection(uid)
            else:
                states[uid].toggle_expand_all()
        event.app.invalidate()

    @bindings.add("m", filter=tree_focus, eager=True)
    def _toggle_selected_memories(event) -> None:
        uid = focused_role_uid()
        if uid is not None and uid in memory_previews:
            memory_previews[uid].toggle_selected_memories()
            if not clear_hidden_memory_selection(uid):
                status["value"] = ""
        event.app.invalidate()

    @bindings.add("M", filter=tree_focus, eager=True)
    def _toggle_all_memories(event) -> None:
        uid = focused_role_uid()
        if uid is not None and uid in memory_previews:
            memory_previews[uid].toggle_all_memories()
            if not clear_hidden_memory_selection(uid):
                status["value"] = ""
        event.app.invalidate()

    @bindings.add("enter", filter=tree_focus, eager=True)
    @bindings.add(" ", filter=tree_focus, eager=True)
    def _select_existing(event) -> None:
        uid = focused_role_uid()
        if uid is None:
            return
        preview = memory_previews.get(uid)
        if preview is not None and preview.memory_focused:
            target = preview.focused_target()
            if not role_memory_focus_active(uid):
                status["value"] = "Read-only Memory preview; this role uses the whole Context."
            elif target is None:
                status["value"] = "That direct item is not a selectable Memory."
            elif target.context_name not in role_by_uid[uid].selectable_names:
                status["value"] = f"{role_title(uid)} is unavailable."
            else:
                states[uid].selected_name = target.context_name
                selections[uid].choose(target.context_name)
                create[uid] = False
                memory_selections[uid].choose(target)
                if uid in descendant_scope:
                    descendant_scope[uid].choice.choose("EXACT")
                try:
                    refresh_new_name_suggestions()
                except (TypeError, ValueError) as error:
                    status["value"] = str(error)
                else:
                    status["value"] = (
                        f"Focused Memory {target.memory_uid[:8]} selected in "
                        f"{target.context_name}."
                    )
            event.app.invalidate()
            return
        name = states[uid].selected_name
        role = role_by_uid[uid]
        if name not in role.selectable_names:
            status["value"] = f"{role_title(uid)} is unavailable."
        elif role.new_parent_locator:
            try:
                draft = new_name_drafts[uid]
                previous = draft.exact_name
                candidate = draft.choose_parent(name)
                selections[uid].choose(name)
                create[uid] = True
                if uid in memory_selections:
                    memory_selections[uid].clear()
                if candidate != new_name_fields[uid].text:
                    updating_new_names.add(uid)
                    try:
                        new_name_fields[uid].set_text(candidate)
                    finally:
                        updating_new_names.remove(uid)
                suggested_new_names[uid] = candidate
                if confirmed_new_names[uid] == previous:
                    confirmed_new_names[uid] = candidate
            except (TypeError, ValueError) as error:
                status["value"] = str(error)
            else:
                status["value"] = (
                    "Parent selected; edited exact name preserved."
                    if draft.edited
                    else ""
                )
        else:
            selections[uid].choose(name)
            create[uid] = False
            if uid in memory_selections:
                memory_selections[uid].clear()
            try:
                refresh_new_name_suggestions()
            except (TypeError, ValueError) as error:
                status["value"] = str(error)
            else:
                status["value"] = ""
        event.app.invalidate()

    @bindings.add("enter", filter=descendant_focus, eager=True)
    @bindings.add(" ", filter=descendant_focus, eager=True)
    def _toggle_descendants(event) -> None:
        uid = focused_role_uid()
        if uid is not None and uid in descendant_controls:
            descendant_scope[uid].move(
                -1 if descendant_scope[uid].include_descendants else 1
            )
            if descendant_scope[uid].include_descendants and uid in memory_selections:
                memory_selections[uid].clear()
            status["value"] = ""
        event.app.invalidate()

    @bindings.add("left", filter=descendant_focus, eager=True)
    def _exact_descendant_scope(event) -> None:
        uid = focused_role_uid()
        if uid is not None and uid in descendant_controls:
            descendant_scope[uid].move(-1)
            status["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=descendant_focus, eager=True)
    def _subtree_descendant_scope(event) -> None:
        uid = focused_role_uid()
        if uid is not None and uid in descendant_controls:
            descendant_scope[uid].move(1)
            if uid in memory_selections:
                memory_selections[uid].clear()
            status["value"] = ""
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(mode_control), eager=True)
    def _previous_mode(event) -> None:
        mode_state.move(-1)
        clear_inactive_memory_selections()
        status["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(mode_control), eager=True)
    def _next_mode(event) -> None:
        mode_state.move(1)
        clear_inactive_memory_selections()
        status["value"] = ""
        event.app.invalidate()

    for uid, editor in new_inputs.items():
        editor_filter = has_focus(editor)

        @bindings.add("enter", filter=editor_filter, eager=True)
        def _accept_new(event, role_uid=uid) -> None:
            try:
                name = new_name_fields[role_uid].validate_candidate()
            except ValueError as error:
                status["value"] = str(error)
                event.app.invalidate()
                return
            confirmed_new_names[role_uid] = name
            create[role_uid] = True
            if role_uid in memory_selections:
                memory_selections[role_uid].clear()
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
    @bind_case_insensitive_key(
        bindings, "q", filter=~new_input_focus, eager=True
    )
    def _cancel(event) -> None:
        event.app.exit(result=None)

    bind_tui_interrupt(bindings, _cancel)

    def render_header() -> str:
        return f" {display_escape_text(title)} · {active_mode().label}"

    def render_footer() -> str:
        uid = focused_role_uid()
        if (
            uid is not None
            and uid in new_inputs
            and app_ref["app"].layout.has_focus(new_inputs[uid])
        ):
            guidance = (
                "Enter continue · Esc back · Tab pane"
                if role_by_uid[uid].new_parent_locator
                else "Enter confirm name · Esc back · Tab pane"
            )
            if status["value"]:
                return f" {display_escape_text(status['value'])} · {guidance}"
            return f" NEW CONTEXT NAME: {guidance}"
        if status["value"]:
            return f" {display_escape_text(status['value'])}"
        if app_ref["app"].layout.has_focus(apply_control):
            return " APPLY: Enter/Space apply · ↑ previous · Tab pane · Q cancel"
        if app_ref["app"].layout.has_focus(mode_control):
            return " MODE: ←/→ choose · ↓ endpoints · Tab endpoints · Q cancel"
        if (
            uid is not None
            and uid in descendant_controls
            and app_ref["app"].layout.has_focus(descendant_controls[uid])
        ):
            return (
                " RANGE: ← this Context only · → include descendants · "
                "Enter/Space toggle · "
                "↑/↓ move · Tab pane · Q cancel"
            )
        if uid is not None and role_by_uid[uid].new_parent_locator:
            memory_hint = (
                memory_visibility_key_hint(memory_previews[uid].tree) + " · "
                if uid in memory_previews
                else ""
            )
            return (
                " "
                + memory_hint
                + "↑/↓ move · ←/→ tree · Enter/Space choose parent · "
                + "Tab pane · Q cancel"
            )
        if uid is not None and uid in memory_previews and memory_previews[uid].memory_focused:
            memory_action = (
                "Enter/Space select this Memory"
                if role_memory_focus_active(uid)
                and memory_previews[uid].focused_target() is not None
                else "read-only preview · Enter/Space does not select"
            )
            return f" {memory_action} · ↑/↓ move · Tab pane · Q cancel"
        memory_hint = (
            memory_visibility_key_hint(memory_previews[uid].tree) + " · "
            if uid is not None and uid in memory_previews
            else ""
        )
        return (
            " "
            + memory_hint
            + "↑/↓ move · ←/→ tree · Enter/Space choose Context · "
            + "Tab pane · Q cancel"
        )

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
    initial_focus = (
        mode_control if len(mode_specs) > 1 else controls[active_mode().active_roles[0]]
    )
    app: Application[EndpointSetupDraft | None] = Application(
        layout=Layout(root, focused_element=initial_focus),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, CONTEXT_PICKER_STYLE]),
    )
    app_ref["app"] = app
    return app.run()
