"""Compact, report-free decisions for execution operations."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    DynamicContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.exact_name import ExactNameInputControl
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.save_location import SaveLocationView
from memcommit.adapters.console.terminal.core.keybindings import bind_case_insensitive_key
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionItem,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
from memcommit.adapters.console.terminal.components.selection import FlatSelectionState, SelectionOption
from memcommit.adapters.console.terminal.components.selection import render_vertical_choice_rows


def _recommended(option_uid: str, label: str) -> bool:
    """Mark only an operation-authored recommendation; never infer one."""

    token = label.casefold().strip()
    return option_uid.rpartition(":")[2].casefold() == "recommended" or token in {
        "recommended",
        "recommendation",
    }


def _choice_text(item: ResolutionItem, index: int) -> str:
    option = item.options[index]
    label = safe_terminal_text(option.label).strip()
    text = safe_terminal_text(option.text).strip()
    content = label if not text or text == label else f"{label} · {text}"
    if _recommended(option.uid, option.label):
        content += " · Recommended"
    return content


def run_compact_resolution_decisions(
    view_or_supplier: ResolutionWorkbenchView | Callable[[], ResolutionWorkbenchView],
    *,
    selected_option: Callable[[str], str | None],
    stage_option: Callable[[str, str], None],
    response_text: Callable[[str], str] | None = None,
    stage_response: Callable[[str, str], None] | None = None,
    response_validator: Callable[[str], None] | None = None,
    response_option_uid: Callable[[str], str | None] | None = None,
    response_title: str = "DIRECTION OR NOTE · OPTIONAL",
    header_label: str | None = None,
    activation_hint: str = "select/apply",
    show_item_navigation: bool = False,
    build_continue_action: Callable[[str | None], ResolutionWorkbenchAction | None],
    continue_label: Callable[[], str],
    destination: SaveLocationView | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
) -> ResolutionWorkbenchAction:
    """Navigate issues and stage choices without rendering the retained report.

    Left/Right changes the issue, Up/Down changes the compact row, and Enter is
    the sole activation grammar for choices, location, and Apply. An answerable
    item has a directly writable one-line Direction or Note box, not a
    replacement editor screen. Staging is process-local and the separated
    Apply row is the operation's confirmation.
    """

    if (response_text is None) != (stage_response is None):
        raise ValueError("Compact Response requires both read and stage callbacks.")

    supplier = (
        view_or_supplier if callable(view_or_supplier) else lambda: view_or_supplier
    )
    initial = supplier()
    items = tuple(
        item
        for item in initial.items
        if item.effective_obligation in {"REQUIRED", "OPTIONAL"}
        and item.response_state != "NOT_APPLICABLE"
    )

    # A recommendation is an operation-authored default, not a positional
    # guess. Stage it in the process-local decision map so Enter can apply an
    # unchanged recommendation without first manufacturing a draft.
    for item in items:
        if selected_option(item.uid) is not None or item.selected_option_uid:
            continue
        recommendations = tuple(
            option for option in item.options if _recommended(option.uid, option.label)
        )
        if len(recommendations) == 1:
            stage_option(item.uid, recommendations[0].uid)

    item_index = {"value": 0}
    if items:
        selected_uid = next(
            (item.uid for item in items if selected_option(item.uid) is not None),
            items[0].uid,
        )
        item_index["value"] = next(
            index for index, item in enumerate(items) if item.uid == selected_uid
        )
    row_index = {"value": 0}
    status = {"value": ""}
    destination_editing = {"value": False}
    syncing_response = {"value": False}
    bindings = KeyBindings()
    destination_field = (
        ExactNameInputControl.create(destination, input_name="compact-save-location")
        if destination is not None
        else None
    )
    response_area = (
        TextArea(
            text="",
            multiline=False,
            prompt="› ",
            focusable=True,
            focus_on_click=True,
            wrap_lines=False,
            width=(
                Dimension(min=24, preferred=48, max=56)
                if response_option_uid is not None
                else Dimension(min=24, preferred=96, max=96)
            ),
            height=Dimension.exact(1),
            dont_extend_width=True,
            name="compact-resolution-response",
            style=(
                "class:memcommit.choice.active"
                if response_option_uid is not None
                else ""
            ),
        )
        if stage_response is not None
        else None
    )
    response_keys_active = (
        has_focus(response_area)
        if response_area is not None
        else Condition(lambda: False)
    )
    destination_keys_active = Condition(lambda: destination_editing["value"])
    decision_keys_active = (
        Condition(lambda: not destination_editing["value"])
        & ~response_keys_active
    )

    def active_item() -> ResolutionItem | None:
        return items[item_index["value"]] if items else None

    def response_available(item: ResolutionItem | None) -> bool:
        return (
            item is not None
            and item.commentable
            and response_text is not None
            and stage_response is not None
        )

    def response_supported(item: ResolutionItem | None) -> bool:
        return (
            response_available(item)
            and response_option_uid is not None
            and item is not None
            and response_option_uid(item.uid) is not None
        )

    def response_selected(item: ResolutionItem | None) -> bool:
        return bool(
            response_available(item)
            and (
                response_option_uid is None
                or (
                    response_supported(item)
                    and item is not None
                    and selected_for(item) == response_option_uid(item.uid)
                )
            )
        )

    def action_rows() -> tuple[SelectionOption, ...]:
        rows: list[SelectionOption] = []
        if response_option_uid is None and response_available(active_item()):
            rows.append(SelectionOption("action:RESPONSE", "Direction or note"))
        if destination is not None:
            rows.append(
                SelectionOption(
                    "action:CHANGE_DESTINATION",
                    f"Change {destination.label.lower()}",
                )
            )
        if show_item_navigation and len(items) > 1:
            rows.extend(
                (
                    SelectionOption("action:PREV", "Previous item"),
                    SelectionOption("action:NEXT", "Next item"),
                )
            )
        rows.append(SelectionOption("action:CONTINUE", continue_label()))
        return tuple(rows)

    def visible_rows() -> tuple[SelectionOption, ...]:
        item = active_item()
        choices = (
            tuple(
                SelectionOption(
                    f"choice:{option.uid}",
                    _choice_text(item, index),
                )
                for index, option in enumerate(item.options)
            )
            if item is not None
            else ()
        )
        return choices + action_rows()

    def row_count() -> int:
        return len(visible_rows())

    def selected_for(item: ResolutionItem) -> str | None:
        return selected_option(item.uid) or item.selected_option_uid

    def focus_selected_choice() -> None:
        item = active_item()
        if item is None:
            row_index["value"] = 0
            return
        selected_uid = selected_for(item)
        row_index["value"] = next(
            (
                index
                for index, option in enumerate(item.options)
                if option.uid == selected_uid
            ),
            0,
        )

    focus_selected_choice()

    def continue_row_label() -> str:
        base = safe_terminal_text(continue_label()).strip().upper()
        if base == "APPLY":
            base = "APPLY ALL"
        required = tuple(
            item for item in items if item.effective_obligation == "REQUIRED"
        )
        if not required:
            return base

        def is_answered(item: ResolutionItem) -> bool:
            selected_uid = selected_for(item)
            if (
                response_option_uid is not None
                and response_text is not None
                and selected_uid == response_option_uid(item.uid)
            ):
                return bool(response_text(item.uid).strip())
            return selected_uid is not None or item.response_state == "ANSWERED"

        answered_count = sum(
            1
            for item in required
            if is_answered(item)
        )
        readiness = " READY" if answered_count == len(required) else ""
        return f"{base} · {answered_count}/{len(required)}{readiness}"

    def render_header() -> list[tuple[str, str]]:
        view = supplier()
        if header_label is not None:
            position = (
                f" · < {item_index['value'] + 1}/{len(items)} >" if items else ""
            )
            return [
                (
                    "class:report-label",
                    f" {safe_terminal_text(header_label).strip()}{position}\n",
                )
            ]
        if items:
            position = f"< {item_index['value'] + 1}/{len(items)} >"
            state = "NEEDS INPUT"
        else:
            position = "READY"
            state = "READY TO APPLY"
        return [
            (
                "class:report-label",
                f" {safe_terminal_text(view.operation.upper())} {state} · {position}\n",
            )
        ]

    def response_choice_index(item: ResolutionItem | None) -> int | None:
        if not response_supported(item) or item is None or response_option_uid is None:
            return None
        target_uid = response_option_uid(item.uid)
        return next(
            (
                index
                for index, option in enumerate(item.options)
                if option.uid == target_uid
            ),
            None,
        )

    def render_intro() -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = []
        if destination is not None:
            fragments.append(
                (
                    "class:report-neutral",
                    f" {safe_terminal_text(destination.label)} · "
                    f"{safe_terminal_text(destination.value)}"
                    + (
                        f" · {safe_terminal_text(destination.state)}"
                        if destination.state
                        else ""
                    )
                    + "\n\n",
                )
            )
        item = active_item()
        if item is not None:
            fragments.append(
                (
                    "class:section",
                    f" {safe_terminal_text(item.display_kind.upper())} · "
                    f"{safe_terminal_text(item.title)}\n",
                )
            )
            if item.question.strip() and item.question.strip() != item.title.strip():
                fragments.append(
                    ("class:report-neutral", f" {safe_terminal_text(item.question)}\n")
                )
        return fragments

    def render_choice_range(*, after_response: bool) -> list[tuple[str, str]]:
        item = active_item()
        if item is None:
            return []
        response_index = response_choice_index(item)
        if response_index is None:
            indexes = range(len(item.options)) if not after_response else range(0)
        elif after_response:
            indexes = range(response_index + 1, len(item.options))
        else:
            indexes = range(0, response_index + 1)
        fragments: list[tuple[str, str]] = []
        selected_uid = selected_for(item)
        content_width = max(30, get_app().output.get_size().columns - 4)
        for index in indexes:
            option = item.options[index]
            row = SelectionOption(f"choice:{option.uid}", _choice_text(item, index))
            state = FlatSelectionState(
                (row,),
                cursor_uid=row.uid,
                selected_uid=(
                    row.uid if selected_uid == option.uid else None
                ),
                allow_empty=True,
            )
            fragments.extend(
                render_vertical_choice_rows(
                    state,
                    focused=(
                        row_index["value"] == index
                        and not (
                            response_area is not None
                            and get_app().layout.has_focus(response_area)
                        )
                    ),
                    content_width=content_width,
                    numbered=False,
                    blank_between=False,
                )
            )
        if not after_response and response_index is not None:
            # This Window and the choice-bound editor are adjacent HSplit
            # children. A final newline creates an empty terminal row between
            # choice 2 and its editor, so let the next child own that row break.
            for fragment_index in range(len(fragments) - 1, -1, -1):
                style, text = fragments[fragment_index]
                if not text:
                    continue
                if text.endswith("\n"):
                    fragments[fragment_index] = (style, text[:-1])
                break
        return fragments

    def render_actions() -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = []
        item = active_item()
        action_offset = len(item.options) if item is not None else 0
        if response_option_uid is None and response_available(item):
            action_offset += 1
        if destination is not None:
            focused = row_index["value"] == action_offset
            fragments.append(
                (
                    focused_control_style(focused=focused, selected=focused),
                    f"  Change {safe_terminal_text(destination.label.lower())}\n",
                )
            )
            action_offset += 1
        if show_item_navigation and len(items) > 1:
            previous_focused = row_index["value"] == action_offset
            next_focused = row_index["value"] == action_offset + 1
            position = f"{item_index['value'] + 1}/{len(items)}"
            fragments.extend(
                (
                    ("", "\n  "),
                    (
                        focused_control_style(
                            focused=previous_focused,
                            selected=previous_focused,
                        ),
                        "[← PREV]",
                    ),
                    (
                        "class:report-neutral",
                        f"        {position}        ",
                    ),
                    (
                        focused_control_style(
                            focused=next_focused,
                            selected=next_focused,
                        ),
                        "[NEXT →]",
                    ),
                    ("", "\n"),
                )
            )
            action_offset += 2
        focused = row_index["value"] == action_offset
        fragments.extend(
            (
                ("", "\n"),
                (
                    focused_control_style(focused=focused, selected=focused),
                    f"  {continue_row_label()}\n",
                ),
            )
        )
        return fragments

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if destination_editing["value"]:
            return " Enter use exact name · Esc return · Ctrl-C cancel"
        if response_area is not None and get_app().layout.has_focus(response_area):
            return " Type your intent · Enter save · ↑/↓ save and choose · Esc freeze"
        return (
            " ←/→ issue · ↑/↓ move · Enter "
            + safe_terminal_text(activation_hint)
            + " · Esc close"
        )

    header_control = FormattedTextControl(render_header)
    body_control = FormattedTextControl(
        lambda: render_intro() + render_choice_range(after_response=False),
        focusable=True,
        show_cursor=False,
    )
    trailing_choice_control = FormattedTextControl(
        lambda: render_choice_range(after_response=True),
        focusable=False,
        show_cursor=False,
    )
    action_control = FormattedTextControl(
        render_actions,
        focusable=True,
        show_cursor=False,
    )
    footer_control = FormattedTextControl(render_footer)
    def render_frozen_response() -> list[tuple[str, str]]:
        item = active_item()
        value = (
            response_text(item.uid).strip()
            if item is not None and response_text is not None
            else ""
        )
        content = safe_terminal_text(value) if value else "Type here…"
        if len(content) > 46:
            content = content[:43].rstrip() + "..."
        value_style = "class:report-neutral" if value else "class:loading-placeholder"
        return [
            ("class:report-label", f"      {safe_terminal_text(response_title)}  │ "),
            (value_style, f"› {content:<46}"),
            ("class:report-neutral", " │\n"),
        ]

    frozen_response_control = FormattedTextControl(render_frozen_response)
    editing_response_row = (
        VSplit(
            [
                Window(
                    FormattedTextControl(
                        lambda: [
                            (
                                "class:report-label",
                                f"      {safe_terminal_text(response_title)}  │ ",
                            )
                        ]
                    ),
                    dont_extend_width=True,
                ),
                response_area,
                Window(
                    FormattedTextControl(
                        lambda: [("class:report-label", " │")]
                    ),
                    width=Dimension.exact(2),
                    dont_extend_width=True,
                ),
                Window(),
            ],
            height=Dimension.exact(1),
        )
        if response_area is not None
        else None
    )
    if response_option_uid is None:
        response_frame = (
            build_focused_frame(
                response_area,
                title="DIRECTION OR NOTE · OPTIONAL",
                is_focused=lambda: get_app().layout.has_focus(response_area),
                height=Dimension.exact(3),
                style="class:report-neutral",
            )
            if response_area is not None
            else None
        )
        inline_response_row = (
            ConditionalContainer(
                VSplit([response_frame, Window()]),
                filter=Condition(lambda: response_available(active_item())),
            )
            if response_frame is not None
            else None
        )
    else:
        inline_response_row = (
            HSplit(
                [
                    ConditionalContainer(
                        editing_response_row,
                        filter=has_focus(response_area),
                    ),
                    ConditionalContainer(
                        Window(
                            frozen_response_control,
                            height=Dimension.exact(1),
                            dont_extend_height=True,
                        ),
                        filter=~has_focus(response_area),
                    ),
                ]
            )
            if editing_response_row is not None and response_area is not None
            else None
        )
    decision_children = [
        Window(body_control, wrap_lines=True, dont_extend_height=True),
    ]
    if inline_response_row is not None:
        if response_option_uid is None:
            decision_children.append(inline_response_row)
        else:
            decision_children.append(
                ConditionalContainer(
                    inline_response_row,
                    filter=Condition(lambda: response_supported(active_item())),
                )
            )
    decision_children.append(
        Window(
            trailing_choice_control,
            wrap_lines=True,
            dont_extend_height=True,
        )
    )
    decision_children.append(
        Window(action_control, wrap_lines=True, dont_extend_height=True)
    )
    decision_body = HSplit(decision_children)

    def active_body():
        if destination_editing["value"] and destination_field is not None:
            return destination_field.input
        return decision_body

    root = build_tui_frame(
        TuiRegion(
            Window(
                header_control,
                height=Dimension.exact(1),
                dont_extend_height=True,
            )
        ),
        TuiRegion(DynamicContainer(active_body)),
        TuiRegion(
            Window(
                footer_control,
                height=Dimension.exact(1),
                dont_extend_height=True,
            )
        ),
    )
    app: Application[ResolutionWorkbenchAction] = Application(
        layout=Layout(root, focused_element=body_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_item(delta: int) -> None:
        if not items:
            return
        item_index["value"] = (item_index["value"] + delta) % len(items)
        focus_selected_choice()
        sync_response_field()
        status["value"] = ""
        get_app().layout.focus(body_control)

    def move_row(delta: int) -> None:
        row_index["value"] = max(
            0,
            min(row_index["value"] + delta, max(row_count() - 1, 0)),
        )
        status["value"] = ""
        item = active_item()
        option_count = len(item.options) if item is not None else 0
        if (
            response_option_uid is None
            and response_area is not None
            and response_available(item)
            and row_index["value"] == option_count
        ):
            sync_response_field()
            get_app().layout.focus(response_area)
        elif row_index["value"] < option_count:
            get_app().layout.focus(body_control)
        else:
            get_app().layout.focus(action_control)

    def finish(action: ResolutionWorkbenchAction | None) -> None:
        if action is None:
            status["value"] = "This action is not ready. Choose a required response."
            return
        app.exit(result=action)

    def select_choice(index: int) -> None:
        item = active_item()
        if item is None or not 0 <= index < len(item.options):
            status["value"] = "That choice is unavailable."
            return
        option = item.options[index]
        stage_option(item.uid, option.uid)
        row_index["value"] = index
        status["value"] = f"Selected · {safe_terminal_text(option.label)}"
        if (
            response_option_uid is not None
            and option.uid == response_option_uid(item.uid)
        ):
            open_response()

    def activate() -> None:
        item = active_item()
        option_count = len(item.options) if item is not None else 0
        if item is not None and row_index["value"] < option_count:
            select_choice(row_index["value"])
            return
        action_uid = action_rows()[row_index["value"] - option_count].uid
        if action_uid == "action:CONTINUE":
            finish(
                build_continue_action(item.uid if item is not None else None)
            )
        elif action_uid == "action:CHANGE_DESTINATION":
            open_destination()
        elif action_uid == "action:PREV":
            move_item(-1)
        elif action_uid == "action:NEXT":
            move_item(1)
        elif action_uid == "action:RESPONSE":
            open_response()
        else:  # pragma: no cover - action rows are closed above
            status["value"] = "That action is unavailable."

    def sync_response_field() -> None:
        item = active_item()
        if (
            not response_available(item)
            or item is None
            or response_area is None
            or response_text is None
        ):
            return
        current = response_text(item.uid).replace("\r", " ").replace("\n", " ")
        syncing_response["value"] = True
        try:
            response_area.text = current
            response_area.buffer.cursor_position = len(current)
        finally:
            syncing_response["value"] = False

    def response_is_valid() -> bool:
        if response_area is None or response_validator is None:
            return True
        try:
            response_validator(response_area.text)
        except (TypeError, ValueError) as error:
            status["value"] = str(error)
            return False
        return True

    def stage_inline_response() -> None:
        item = active_item()
        if (
            syncing_response["value"]
            or item is None
            or response_area is None
            or stage_response is None
            or not response_available(item)
            or not response_is_valid()
        ):
            return
        stage_response(item.uid, response_area.text)
        status["value"] = ""

    def open_response() -> None:
        if response_area is None or not response_selected(active_item()):
            return
        sync_response_field()
        status["value"] = ""
        get_app().layout.focus(response_area)

    def leave_response(delta: int) -> None:
        if not response_is_valid():
            return
        stage_inline_response()
        row_index["value"] = max(
            0,
            min(row_index["value"] + delta, max(row_count() - 1, 0)),
        )
        status["value"] = ""
        item = active_item()
        option_count = len(item.options) if item is not None else 0
        get_app().layout.focus(
            body_control if row_index["value"] < option_count else action_control
        )

    if response_area is not None:
        if response_option_uid is None:
            response_area.buffer.on_text_changed += (
                lambda _buffer: stage_inline_response()
            )
        sync_response_field()

    def open_destination() -> None:
        if destination is None or destination_field is None:
            return
        destination_field.set_text(destination.value)
        destination_editing["value"] = True
        status["value"] = ""
        get_app().layout.focus(destination_field.input)

    def close_destination() -> None:
        destination_editing["value"] = False
        status["value"] = ""
        get_app().layout.focus(action_control)

    def submit_destination() -> None:
        if destination_field is None:
            return
        try:
            value = destination_field.validate_candidate()
        except ValueError as error:
            status["value"] = str(error)
            return
        app.exit(
            result=ResolutionWorkbenchAction(
                kind="CHANGE_DESTINATION",
                destination=value,
            )
        )

    @bindings.add("left", filter=decision_keys_active, eager=True)
    def _left(event) -> None:
        move_item(-1)
        event.app.invalidate()

    @bindings.add("right", filter=decision_keys_active, eager=True)
    def _right(event) -> None:
        move_item(1)
        event.app.invalidate()

    @bindings.add("up", filter=decision_keys_active, eager=True)
    def _up(event) -> None:
        move_row(-1)
        event.app.invalidate()

    @bindings.add("down", filter=decision_keys_active, eager=True)
    def _down(event) -> None:
        move_row(1)
        event.app.invalidate()

    @bindings.add("enter", filter=decision_keys_active, eager=True)
    def _enter(event) -> None:
        activate()
        event.app.invalidate()

    def close_or_back(event) -> None:
        event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

    @bindings.add("escape", filter=decision_keys_active, eager=True)
    @bindings.add("backspace", filter=decision_keys_active, eager=True)
    def _back(event) -> None:
        close_or_back(event)

    @bindings.add("escape", filter=destination_keys_active, eager=True)
    def _destination_back(event) -> None:
        close_destination()
        event.app.invalidate()

    @bindings.add("enter", filter=destination_keys_active, eager=True)
    def _destination_submit(event) -> None:
        submit_destination()
        event.app.invalidate()

    @bindings.add("escape", filter=response_keys_active, eager=True)
    def _response_back(event) -> None:
        if response_option_uid is None:
            # The generic compact shell retains its established note-field
            # behavior. Resolve opts into the choice-bound frozen draft below.
            sync_response_field()
            event.app.layout.focus(body_control)
        else:
            leave_response(0)
        event.app.invalidate()

    @bindings.add("enter", filter=response_keys_active, eager=True)
    def _response_submit(event) -> None:
        leave_response(0 if response_option_uid is not None else 1)
        event.app.invalidate()

    @bindings.add("up", filter=response_keys_active, eager=True)
    def _response_up(event) -> None:
        leave_response(-1)
        event.app.invalidate()

    @bindings.add("down", filter=response_keys_active, eager=True)
    def _response_down(event) -> None:
        leave_response(1)
        event.app.invalidate()

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bind_case_insensitive_key(
        bindings,
        "q",
        filter=decision_keys_active,
        eager=True,
    )
    def _close(event) -> None:
        event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return ResolutionWorkbenchAction(kind="CLOSE")


__all__ = ["run_compact_resolution_decisions"]
