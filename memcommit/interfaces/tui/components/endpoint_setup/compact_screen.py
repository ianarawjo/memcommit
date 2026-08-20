"""Compact, input-first presentation for shared Endpoint Setup drafts."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    Float,
    FloatContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.context_targeting.tui.reach import ContextReachState
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.tui.components.endpoint_setup.memory_focus import (
    EndpointMemoryFocusController,
    MemoryProjectionLoader,
)
from memcommit.interfaces.tui.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
)
from memcommit.interfaces.tui.components.exact_name import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.interfaces.tui.core.keybindings import bind_case_insensitive_key
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    focused_control_style,
)
from memcommit.selection.tui import choice_marker, choice_visual_state
from memcommit.source_projection.presentation import source_display_text


DraftValidator = Callable[[EndpointSetupDraft], str | None]


def run_compact_endpoint_setup(
    spec: EndpointSetupSpec,
    *,
    memory_loader: MemoryProjectionLoader | None,
    validate_draft: DraftValidator | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> EndpointSetupDraft | None:
    """Collect the same typed draft through a five-row, input-first form."""

    if spec.screen_layout != "COMPACT_FORM":
        raise ValueError("Compact Endpoint Setup requires COMPACT_FORM layout.")
    if require_tty:
        require_interactive_terminal(
            spec.title,
            snapshot_hint="Pass explicit Context operands outside a terminal.",
        )
    memory_roles = tuple(role for role in spec.roles if role.allow_memory_focus)
    if memory_roles and memory_loader is None:
        raise ValueError("Endpoint Memory focus requires a projection loader.")

    status = {"value": ""}
    role_by_uid = {role.uid: role for role in spec.roles}
    mode_state = HorizontalChoiceState(
        tuple(
            HorizontalChoiceOption(mode.uid, mode.label, mode.description)
            for mode in spec.modes
        ),
        selected_uid=spec.initial_mode_uid,
    )

    def selected_mode_uid() -> str:
        return mode_state.selected_uid

    def role_is_active(role_uid: str) -> bool:
        return role_uid in spec.active_role_uids(selected_mode_uid())

    def role_allows_descendants(role_uid: str) -> bool:
        return spec.role_allows_descendants(selected_mode_uid(), role_uid)

    def role_allows_memory_focus(role_uid: str) -> bool:
        return spec.role_allows_memory_focus(selected_mode_uid(), role_uid)

    def completion_metadata(role: EndpointSetupRole) -> dict[str, str]:
        annotations = dict(role.annotations)
        result: dict[str, str] = {}
        for name in role.names:
            if name not in role.selectable_names:
                continue
            values: list[str] = []
            if name == role.current_context:
                values.append("CURRENT")
            annotation = source_display_text(annotations.get(name))
            if annotation:
                values.append(annotation)
            result[name] = " · ".join(values)
        return result

    role_name_controls: dict[str, ExactNameInputControl] = {}
    role_inputs: dict[str, TextArea] = {}
    catalog_selectors: dict[str, ContextSelectorControl] = {}
    for role in spec.roles:
        initial = (
            role.initial_new_name
            if role.allow_new and role.prefer_new
            else role.selected_name
        )
        candidates = tuple(name for name in role.names if name in role.selectable_names)
        completer = WordCompleter(
            candidates,
            meta_dict=completion_metadata(role),
            sentence=True,
            match_middle=True,
        )
        input_control = ExactNameInputControl.create(
            ExactNameFieldView(
                value=initial,
                label="CONTEXT",
                detail="Enter one exact existing or operation-valid new Context name.",
                value_label="Context name",
            ),
            input_name=f"compact-endpoint-{role.uid.casefold()}",
            prompt="› ",
            completer=completer,
            complete_while_typing=True,
            width=Dimension(min=18, preferred=42, max=52),
            dont_extend_width=True,
        )
        role_name_controls[role.uid] = input_control
        role_inputs[role.uid] = input_control.input
        if candidates:
            selected = initial if initial in role.selectable_names else candidates[0]
            selector = ContextSelectorControl(
                ContextSelectorView(
                    names=candidates,
                    selected=(selected,),
                    label=f"{role.label} · ALL ALLOWED",
                    current_context=role.current_context,
                    annotations=tuple(
                        (name, annotation)
                        for name, annotation in role.annotations
                        if name in role.selectable_names
                    ),
                ),
                height=min(8, max(3, len(candidates))),
            )
            # This transient view promises the complete frozen role catalog,
            # so lexical branches start expanded instead of hiding candidates.
            selector.toggle_expand_all()
            catalog_selectors[role.uid] = selector

    reach_states = {
        role.uid: ContextReachState.create(include_descendants=role.include_descendants)
        for role in spec.roles
        if role.allow_descendants
    }
    memory_focuses = {
        role.uid: EndpointMemoryFocusController(
            role.uid,
            selected_context=(lambda uid=role.uid: role_inputs[uid].text.strip()),
            loader=memory_loader,
            selected_memory_uid=role.selected_memory_uid,
        )
        for role in memory_roles
    }
    memory_detail = {"role_uid": None}
    catalog_detail = {"role_uid": None}

    def clear_stale_memory(role_uid: str) -> None:
        memory_focus = memory_focuses.get(role_uid)
        if memory_focus is not None:
            memory_focus.clear()
        if memory_detail["role_uid"] == role_uid:
            memory_detail["role_uid"] = None

    for role_uid, input_area in role_inputs.items():
        input_area.buffer.on_text_changed += (
            lambda _buffer, uid=role_uid: clear_stale_memory(uid)
        )

    def resolve_role(role_uid: str) -> tuple[str, bool]:
        role = role_by_uid[role_uid]
        candidate = role_inputs[role_uid].text.strip()
        if not candidate:
            raise ValueError(
                f"{spec.role_label(selected_mode_uid(), role_uid)} needs a Context name."
            )
        if candidate in role.selectable_names:
            return candidate, False
        if not role.allow_new:
            raise ValueError(
                f"{spec.role_label(selected_mode_uid(), role_uid)} requires an existing readable Context."
            )
        if role.new_name_validator is not None:
            role.new_name_validator(candidate)
        return candidate, True

    def make_draft() -> EndpointSetupDraft:
        values: list[EndpointSetupValue] = []
        for role_uid in spec.active_role_uids(selected_mode_uid()):
            context_name, create = resolve_role(role_uid)
            descendants = (
                reach_states[role_uid].include_descendants
                if not create
                and role_uid in reach_states
                and role_allows_descendants(role_uid)
                else False
            )
            memory_uid = (
                memory_focuses[role_uid].selected_memory_uid
                if not create
                and not descendants
                and role_uid in memory_focuses
                and role_allows_memory_focus(role_uid)
                else None
            )
            values.append(
                EndpointSetupValue(
                    role_uid,
                    context_name,
                    include_descendants=descendants,
                    memory_uid=memory_uid,
                    create=create,
                )
            )
        return EndpointSetupDraft(selected_mode_uid(), tuple(values))

    mode_control: FormattedTextControl

    def render_mode() -> StyleAndTextTuples:
        return render_horizontal_choice(
            mode_state,
            title="MODE",
            focused=get_app().layout.has_focus(mode_control),
            inline_boxed=True,
        )

    mode_control = FormattedTextControl(
        render_mode,
        focusable=True,
        show_cursor=False,
    )
    mode_line = Window(
        mode_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
        wrap_lines=False,
    )

    role_label_controls: dict[str, FormattedTextControl] = {}
    role_state_controls: dict[str, FormattedTextControl] = {}
    browse_controls: dict[str, FormattedTextControl] = {}
    reach_controls: dict[str, FormattedTextControl] = {}
    memory_controls: dict[str, FormattedTextControl] = {}

    def role_row_focused(role_uid: str) -> bool:
        controls: list[object] = [role_inputs[role_uid]]
        if role_uid in browse_controls:
            controls.append(browse_controls[role_uid])
        if role_uid in reach_controls:
            controls.append(reach_controls[role_uid])
        if role_uid in memory_controls:
            controls.append(memory_controls[role_uid])
        return any(get_app().layout.has_focus(control) for control in controls)

    def render_role_label(role_uid: str) -> StyleAndTextTuples:
        focused = role_row_focused(role_uid)
        return [
            (
                focused_control_style(focused=focused),
                f"{'›' if focused else ' '} "
                f"{safe_terminal_text(spec.role_label(selected_mode_uid(), role_uid))}",
            )
        ]

    def render_role_state(role_uid: str) -> StyleAndTextTuples:
        role = role_by_uid[role_uid]
        candidate = role_inputs[role_uid].text.strip()
        if not candidate:
            if role.allow_new:
                label = (
                    "CHOOSE EMPTY OR ENTER NEW NAME"
                    if role_uid in browse_controls
                    else "ENTER NEW NAME"
                )
            else:
                label = "TYPE CONTEXT"
            style = "class:source-state"
        elif candidate in role.selectable_names:
            values = []
            if role.allow_new:
                values.append("EMPTY · EXISTING")
            if candidate == role.current_context:
                values.append("CURRENT")
            annotation = source_display_text(dict(role.annotations).get(candidate))
            if annotation:
                values.append(annotation)
            label = " · ".join(values)
            style = "class:source-access"
        elif role.allow_new:
            label = "NEW · NOT CREATED"
            style = "class:source-state"
        else:
            completion_state = role_inputs[role_uid].buffer.complete_state
            match_count = (
                len(completion_state.completions) if completion_state is not None else 0
            )
            label = f"{match_count} MATCHES" if match_count else "UNAVAILABLE"
            style = "class:source-state"
        return [(style, safe_terminal_text(label))]

    def render_reach(role_uid: str) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(reach_controls[role_uid])
        selected = reach_states[role_uid].include_descendants
        visual = choice_visual_state(
            cursor=True,
            selected=selected,
            focused=focused,
        )
        return [
            (visual.border_style, "["),
            (
                visual.content_style,
                f" {choice_marker(selected=selected)} INCLUDE DESCENDANTS ",
            ),
            (visual.border_style, "]"),
        ]

    def render_browse(role_uid: str) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(browse_controls[role_uid])
        return [
            (
                focused_control_style(focused=focused, selected=focused),
                "[ BROWSE ]",
            )
        ]

    def render_memory(role_uid: str) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(memory_controls[role_uid])
        descendants = reach_states[role_uid].include_descendants
        selected_memory = memory_focuses[role_uid].selected_memory_uid
        value = (
            "WHOLE SUBTREE"
            if descendants
            else selected_memory[:8]
            if selected_memory is not None
            else "WHOLE CONTEXT"
        )
        return [
            (
                focused_control_style(
                    focused=focused,
                    selected=selected_memory is not None and not descendants,
                ),
                f"[ MEMORY · {safe_terminal_text(value)} ]",
            )
        ]

    label_width = max(
        7,
        max(
            len(spec.role_label(mode.uid, role.uid)) + 3
            for mode in spec.modes
            for role in spec.roles
            if role.uid in spec.active_role_uids(mode.uid)
        ),
    )
    role_rows = []
    for role in spec.roles:
        role_label_controls[role.uid] = FormattedTextControl(
            lambda uid=role.uid: render_role_label(uid),
            show_cursor=False,
        )
        role_state_controls[role.uid] = FormattedTextControl(
            lambda uid=role.uid: render_role_state(uid),
            show_cursor=False,
        )
        if role.uid in catalog_selectors:
            browse_controls[role.uid] = FormattedTextControl(
                lambda uid=role.uid: render_browse(uid),
                focusable=True,
                show_cursor=False,
            )
        if role.allow_descendants:
            reach_controls[role.uid] = FormattedTextControl(
                lambda uid=role.uid: render_reach(uid),
                focusable=True,
                show_cursor=False,
            )
        if role.allow_memory_focus:
            memory_controls[role.uid] = FormattedTextControl(
                lambda uid=role.uid: render_memory(uid),
                focusable=True,
                show_cursor=False,
            )

        columns = [
            Window(
                role_label_controls[role.uid],
                width=Dimension.exact(label_width),
                dont_extend_height=True,
            ),
            role_inputs[role.uid],
        ]
        if role.uid in browse_controls:
            columns.append(
                Window(
                    browse_controls[role.uid],
                    width=Dimension.exact(11),
                    dont_extend_height=True,
                )
            )
        columns.extend(
            [
                Window(
                    role_state_controls[role.uid],
                    width=Dimension(min=0, preferred=31, max=34),
                    dont_extend_height=True,
                ),
            ]
        )
        if role.uid in reach_controls:
            columns.append(
                ConditionalContainer(
                    Window(
                        reach_controls[role.uid],
                        width=Dimension.exact(27),
                        dont_extend_height=True,
                    ),
                    filter=Condition(lambda uid=role.uid: role_allows_descendants(uid)),
                )
            )
        if role.uid in memory_controls:
            columns.append(
                ConditionalContainer(
                    Window(
                        memory_controls[role.uid],
                        width=Dimension.exact(27),
                        dont_extend_height=True,
                    ),
                    filter=Condition(
                        lambda uid=role.uid: role_allows_memory_focus(uid)
                    ),
                )
            )
        role_rows.append(
            ConditionalContainer(
                VSplit(columns, height=Dimension.exact(1)),
                filter=Condition(lambda uid=role.uid: role_is_active(uid)),
            )
        )

    action_control: FormattedTextControl

    def render_action() -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(action_control)
        return [
            (
                focused_control_style(focused=focused, selected=focused),
                f"{'›' if focused else ' '} [ {safe_terminal_text(spec.action_label)} ]",
            )
        ]

    action_control = FormattedTextControl(
        render_action,
        focusable=True,
        show_cursor=False,
    )
    action_line = Window(
        action_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    catalog_detail_containers = []
    for role_uid, selector in catalog_selectors.items():
        catalog_detail_containers.append(
            ConditionalContainer(
                HSplit(
                    [
                        Window(
                            FormattedTextControl(
                                lambda uid=role_uid: (
                                    "  CONTEXTS · "
                                    f"{safe_terminal_text(spec.role_label(selected_mode_uid(), uid))}"
                                    " · ALL ALLOWED"
                                )
                            ),
                            height=Dimension.exact(1),
                            dont_extend_height=True,
                        ),
                        Window(
                            selector.control,
                            wrap_lines=False,
                            right_margins=[ScrollbarMargin(display_arrows=True)],
                            height=Dimension.exact(min(8, len(selector.view.names))),
                            dont_extend_height=True,
                        ),
                    ]
                ),
                filter=Condition(
                    lambda uid=role_uid: catalog_detail["role_uid"] == uid
                ),
            )
        )

    memory_detail_control: FormattedTextControl

    def render_memory_detail() -> StyleAndTextTuples:
        role_uid = memory_detail["role_uid"]
        if role_uid is None:
            return []
        context_name = role_inputs[role_uid].text.strip()
        fragments: StyleAndTextTuples = [
            (
                "class:report-neutral",
                f"  MEMORY · {safe_terminal_text(spec.role_label(selected_mode_uid(), role_uid))}"
                f" · {display_escape_text(context_name)}\n",
            )
        ]
        fragments.extend(
            memory_focuses[role_uid].render(
                focused=True,
                include_descendants=False,
            )
        )
        return fragments

    memory_detail_control = FormattedTextControl(
        render_memory_detail,
        focusable=False,
        show_cursor=False,
    )
    memory_detail_container = ConditionalContainer(
        Window(
            memory_detail_control,
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
            height=Dimension(min=3, preferred=7, max=9),
        ),
        filter=Condition(lambda: memory_detail["role_uid"] is not None),
    )

    header = Window(
        FormattedTextControl(
            f" {safe_terminal_text(spec.title)} · {safe_terminal_text(spec.subtitle)}"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    footer_control = FormattedTextControl()
    footer = Window(
        footer_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    body = HSplit(
        [
            header,
            mode_line,
            *role_rows,
            action_line,
            *catalog_detail_containers,
            memory_detail_container,
            footer,
        ]
    )
    root = FloatContainer(
        content=body,
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(
                    max_height=8,
                    scroll_offset=1,
                    display_arrows=True,
                ),
            )
        ],
    )

    bindings = KeyBindings()

    def move_mode(_event, delta: int) -> SurfaceMoveResult:
        changed = mode_state.move(delta)
        for role_uid, memory_focus in memory_focuses.items():
            if not role_allows_memory_focus(role_uid):
                memory_focus.clear()
        memory_detail["role_uid"] = None
        catalog_detail["role_uid"] = None
        status["value"] = ""
        return "MOVED" if changed else "BOUNDARY"

    def choose_mode(_event) -> SurfaceActionResult:
        status["value"] = ""
        return "HANDLED"

    def move_role(event, role_uid: str, delta: int) -> SurfaceMoveResult:
        buffer = role_inputs[role_uid].buffer
        if buffer.complete_state is None:
            return "BOUNDARY"
        if delta > 0:
            buffer.complete_next()
        else:
            buffer.complete_previous()
        return "CONSUMED"

    def choose_role(event, role_uid: str) -> SurfaceActionResult:
        buffer = role_inputs[role_uid].buffer
        if (
            buffer.complete_state is not None
            and buffer.complete_state.current_completion is not None
        ):
            buffer.apply_completion(buffer.complete_state.current_completion)
            status["value"] = ""
            return "HANDLED"
        try:
            resolve_role(role_uid)
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
        else:
            status["value"] = ""
            surfaces.focus_relative(event.app, 1, wrap=False)
            if role_uid in browse_controls:
                # Enter confirms direct input and advances to the next semantic
                # control; Tab remains the explicit path into adjacent Browse.
                surfaces.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def open_catalog(event, role_uid: str) -> bool:
        selector = catalog_selectors.get(role_uid)
        if selector is None:
            status["value"] = (
                f"{spec.role_label(selected_mode_uid(), role_uid)} has no eligible "
                "existing Context; type one new exact name."
            )
            return False
        buffer = role_inputs[role_uid].buffer
        if buffer.complete_state is not None:
            buffer.cancel_completion()
        candidate = role_inputs[role_uid].text.strip()
        selected = (
            candidate if candidate in selector.selectable else selector.view.names[0]
        )
        selector.select_name(selected)
        memory_detail["role_uid"] = None
        catalog_detail["role_uid"] = role_uid
        status["value"] = ""
        event.app.layout.focus(selector.control)
        return True

    def move_catalog(_event, role_uid: str, delta: int) -> SurfaceMoveResult:
        selector = catalog_selectors[role_uid]
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def close_catalog(event, *, choose: bool) -> SurfaceActionResult:
        role_uid = catalog_detail["role_uid"]
        if role_uid is None:
            return "IGNORED"
        if choose:
            selector = catalog_selectors[role_uid]
            selector.choose_cursor()
            role_name_controls[role_uid].set_text(selector.tree.selected_name)
        catalog_detail["role_uid"] = None
        status["value"] = ""
        event.app.layout.focus(browse_controls[role_uid])
        return "HANDLED"

    def choose_catalog(event, _role_uid: str) -> SurfaceActionResult:
        return close_catalog(event, choose=True)

    def choose_browse(event, role_uid: str) -> SurfaceActionResult:
        open_catalog(event, role_uid)
        return "HANDLED"

    def prepare_browse(role_uid: str) -> None:
        buffer = role_inputs[role_uid].buffer
        if buffer.complete_state is not None:
            buffer.cancel_completion()

    def move_reach(_event, role_uid: str, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def set_reach(role_uid: str, *, include_descendants: bool) -> None:
        reach_states[role_uid].move(1 if include_descendants else -1)
        if reach_states[role_uid].include_descendants:
            cleared = memory_focuses.get(role_uid)
            if cleared is not None and cleared.clear():
                status["value"] = (
                    f"{spec.role_label(selected_mode_uid(), role_uid)} Memory focus cleared for descendants."
                )
            else:
                status["value"] = ""
            if memory_detail["role_uid"] == role_uid:
                memory_detail["role_uid"] = None
        else:
            status["value"] = ""

    def choose_reach(_event, role_uid: str) -> SurfaceActionResult:
        set_reach(
            role_uid,
            include_descendants=not reach_states[role_uid].include_descendants,
        )
        return "HANDLED"

    def open_memory(role_uid: str) -> bool:
        if reach_states[role_uid].include_descendants:
            memory_focuses[role_uid].clear()
            status["value"] = "Focused Memory requires THIS CONTEXT ONLY."
            return False
        try:
            context_name, create = resolve_role(role_uid)
            if create:
                raise ValueError("A new Context cannot select an existing Memory.")
            memory_focuses[role_uid].prepare_context(context_name)
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
            return False
        memory_detail["role_uid"] = role_uid
        status["value"] = ""
        return True

    def move_memory(_event, role_uid: str, delta: int) -> SurfaceMoveResult:
        if memory_detail["role_uid"] != role_uid:
            if not open_memory(role_uid):
                return "CONSUMED"
        memory_focuses[role_uid].move(delta)
        status["value"] = ""
        return "CONSUMED"

    def choose_memory(_event, role_uid: str) -> SurfaceActionResult:
        if memory_detail["role_uid"] != role_uid:
            open_memory(role_uid)
            return "HANDLED"
        selected = memory_focuses[role_uid].choose()
        memory_detail["role_uid"] = None
        status["value"] = (
            f"{spec.role_label(selected_mode_uid(), role_uid)} uses Memory {selected[:8]}."
            if selected is not None
            else f"{spec.role_label(selected_mode_uid(), role_uid)} uses the whole Context."
        )
        return "HANDLED"

    def finish(event) -> SurfaceActionResult:
        try:
            draft = make_draft()
            message = validate_draft(draft) if validate_draft is not None else None
            if message:
                raise ValueError(message)
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(result=draft)
        return "HANDLED"

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        catalog_role_uid = catalog_detail["role_uid"]
        if catalog_role_uid is not None:
            selector = catalog_selectors[catalog_role_uid]
            return (
                FocusSurface(
                    f"CATALOG:{catalog_role_uid}",
                    selector.control,
                    move_vertical=(
                        lambda event, delta, uid=catalog_role_uid: move_catalog(
                            event, uid, delta
                        )
                    ),
                    activate=(
                        lambda event, uid=catalog_role_uid: choose_catalog(event, uid)
                    ),
                ),
            )
        values: list[FocusSurface] = [
            FocusSurface(
                "MODE",
                mode_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=choose_mode,
            )
        ]
        for role_uid in spec.active_role_uids(selected_mode_uid()):
            values.append(
                FocusSurface(
                    f"ROLE:{role_uid}",
                    role_inputs[role_uid],
                    move_vertical=(
                        lambda event, delta, uid=role_uid: move_role(event, uid, delta)
                    ),
                    activate=(lambda event, uid=role_uid: choose_role(event, uid)),
                )
            )
            if role_uid in browse_controls:
                values.append(
                    FocusSurface(
                        f"BROWSE:{role_uid}",
                        browse_controls[role_uid],
                        move_vertical=lambda _event, _delta: "BOUNDARY",
                        activate=(
                            lambda event, uid=role_uid: choose_browse(event, uid)
                        ),
                        on_focus=lambda uid=role_uid: prepare_browse(uid),
                    )
                )
            if role_uid in reach_controls and role_allows_descendants(role_uid):
                values.append(
                    FocusSurface(
                        f"RANGE:{role_uid}",
                        reach_controls[role_uid],
                        move_vertical=(
                            lambda event, delta, uid=role_uid: move_reach(
                                event, uid, delta
                            )
                        ),
                        activate=(lambda event, uid=role_uid: choose_reach(event, uid)),
                    )
                )
            if role_uid in memory_controls and role_allows_memory_focus(role_uid):
                values.append(
                    FocusSurface(
                        f"MEMORY:{role_uid}",
                        memory_controls[role_uid],
                        move_vertical=(
                            lambda event, delta, uid=role_uid: move_memory(
                                event, uid, delta
                            )
                        ),
                        activate=(
                            lambda event, uid=role_uid: choose_memory(event, uid)
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

    def focused_reach_role() -> str | None:
        return next(
            (
                role_uid
                for role_uid, control in reach_controls.items()
                if get_app().layout.has_focus(control)
            ),
            None,
        )

    @bindings.add("left", filter=reach_focus, eager=True)
    def _exact_reach(event) -> None:
        role_uid = focused_reach_role()
        if role_uid is not None:
            set_reach(role_uid, include_descendants=False)
        event.app.invalidate()

    @bindings.add("right", filter=reach_focus, eager=True)
    def _descendant_reach(event) -> None:
        role_uid = focused_reach_role()
        if role_uid is not None:
            set_reach(role_uid, include_descendants=True)
        event.app.invalidate()

    @bindings.add(" ", filter=reach_focus, eager=True)
    def _toggle_reach(event) -> None:
        role_uid = focused_reach_role()
        if role_uid is not None:
            choose_reach(event, role_uid)
        event.app.invalidate()

    input_focus = Condition(
        lambda: any(
            get_app().layout.has_focus(input_area)
            for input_area in role_inputs.values()
        )
    )
    browse_focus = Condition(
        lambda: any(
            get_app().layout.has_focus(control) for control in browse_controls.values()
        )
    )

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        if catalog_detail["role_uid"] is not None:
            close_catalog(event, choose=False)
        elif memory_detail["role_uid"] is not None:
            memory_detail["role_uid"] = None
            status["value"] = ""
        elif input_focus():
            buffer = event.current_buffer
            if buffer.complete_state is not None:
                buffer.cancel_completion()
            else:
                event.app.exit(result=None)
        else:
            event.app.exit(result=None)
        event.app.invalidate()

    @bindings.add("c-c", eager=True)
    @bind_case_insensitive_key(
        bindings,
        "q",
        filter=~input_focus,
        eager=True,
    )
    def _close(event) -> None:
        event.app.exit(result=None)

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if catalog_detail["role_uid"] is not None:
            return " ↑/↓ Context · Enter use exact name · Esc close all"
        if get_app().layout.has_focus(mode_control):
            return " ←/→ mode · ↓ FROM · Tab next · Esc cancel"
        if input_focus():
            return " Type exact Context · ↑/↓ matches · Enter confirm · Tab next · Esc cancel"
        if browse_focus():
            return " Enter browse all allowed Contexts · Tab next · Esc cancel"
        if reach_focus():
            return " ←/→, Space, or Enter toggle descendants · Tab next · Esc cancel"
        if any(
            get_app().layout.has_focus(control) for control in memory_controls.values()
        ):
            if memory_detail["role_uid"] is not None:
                return " ↑/↓ Memory · Enter choose · Esc close details"
            return " Enter open Memory choices · Tab next · Esc cancel"
        if get_app().layout.has_focus(action_control):
            return " Enter start Meld · ↑ previous · Esc cancel"
        return " Tab next · Esc cancel"

    footer_control.text = render_footer
    app: Application[EndpointSetupDraft | None] = Application(
        layout=Layout(root, focused_element=mode_control),
        key_bindings=bindings,
        full_screen=False,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE]),
    )
    return app.run()
