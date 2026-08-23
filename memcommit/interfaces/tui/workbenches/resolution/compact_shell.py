"""Compact, report-free decisions for execution operations."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    Dimension,
    DynamicContainer,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.exact_name import ExactNameInputControl
from memcommit.interfaces.tui.components.frame import TuiRegion, build_tui_frame
from memcommit.interfaces.tui.components.save_location import SaveLocationView
from memcommit.interfaces.tui.core.keybindings import bind_case_insensitive_key
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.resolution_workbench import (
    ResolutionItem,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
from memcommit.selection import FlatSelectionState, SelectionOption
from memcommit.selection.tui import render_vertical_choice_rows


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
    build_continue_action: Callable[[str | None], ResolutionWorkbenchAction | None],
    continue_label: Callable[[], str],
    destination: SaveLocationView | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
) -> ResolutionWorkbenchAction:
    """Navigate issues and stage choices without rendering the retained report.

    Left/Right changes the issue, Up/Down changes the compact row, and Enter is
    the sole activation grammar for choices, location, and Apply. Staging is
    process-local and the separated Apply row is the operation's confirmation.
    """

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
    bindings = KeyBindings()
    destination_field = (
        ExactNameInputControl.create(destination, input_name="compact-save-location")
        if destination is not None
        else None
    )
    decision_keys_active = Condition(lambda: not destination_editing["value"])
    destination_keys_active = Condition(lambda: destination_editing["value"])

    def active_item() -> ResolutionItem | None:
        return items[item_index["value"]] if items else None

    def action_rows() -> tuple[SelectionOption, ...]:
        rows: list[SelectionOption] = []
        if destination is not None:
            rows.append(
                SelectionOption(
                    "action:CHANGE_DESTINATION",
                    f"Change {destination.label.lower()}",
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
        answered = sum(
            1
            for item in required
            if selected_for(item) is not None or item.response_state == "ANSWERED"
        )
        readiness = " READY" if answered == len(required) else ""
        return f"{base} · {answered}/{len(required)}{readiness}"

    def render_header() -> list[tuple[str, str]]:
        view = supplier()
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

    def render_body() -> list[tuple[str, str]]:
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
        option_rows = visible_rows()[: len(item.options) if item is not None else 0]
        if option_rows:
            choice_uid = selected_for(item) if item is not None else None
            cursor_uid = (
                option_rows[row_index["value"]].uid
                if row_index["value"] < len(option_rows)
                else (
                    f"choice:{choice_uid}"
                    if choice_uid is not None
                    else option_rows[0].uid
                )
            )
            state = FlatSelectionState(
                option_rows,
                cursor_uid=cursor_uid,
                selected_uid=(
                    f"choice:{choice_uid}" if choice_uid is not None else None
                ),
                allow_empty=True,
            )
            fragments.extend(
                render_vertical_choice_rows(
                    state,
                    focused=row_index["value"] < len(option_rows),
                    content_width=max(30, get_app().output.get_size().columns - 4),
                    numbered=False,
                    blank_between=False,
                )
            )
        action_offset = len(option_rows)
        if destination is not None:
            focused = row_index["value"] == action_offset
            fragments.append(
                (
                    focused_control_style(focused=focused, selected=focused),
                    f"  Change {safe_terminal_text(destination.label.lower())}\n",
                )
            )
            action_offset += 1
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
        return " ←/→ issue · ↑/↓ move · Enter select/apply · Esc close"

    header_control = FormattedTextControl(render_header)
    body_control = FormattedTextControl(render_body, focusable=True, show_cursor=False)
    footer_control = FormattedTextControl(render_footer)

    def active_body():
        if destination_editing["value"] and destination_field is not None:
            return destination_field.input
        return Window(body_control, wrap_lines=True)

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
        status["value"] = ""

    def move_row(delta: int) -> None:
        row_index["value"] = max(
            0,
            min(row_index["value"] + delta, max(row_count() - 1, 0)),
        )
        status["value"] = ""

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
        else:
            open_destination()

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
        get_app().layout.focus(body_control)

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
