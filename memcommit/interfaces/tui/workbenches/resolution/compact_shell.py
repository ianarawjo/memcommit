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

from memcommit.exact_command_review import ExactCommandReview
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.exact_name import ExactNameInputControl
from memcommit.interfaces.tui.components.exact_command_review.rendering import (
    render_exact_command_review,
)
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
        content += " (Recommended)"
    return content


def run_compact_resolution_decisions(
    view_or_supplier: ResolutionWorkbenchView | Callable[[], ResolutionWorkbenchView],
    *,
    selected_option: Callable[[str], str | None],
    stage_option: Callable[[str, str], None],
    build_continue_action: Callable[[str | None], ResolutionWorkbenchAction | None],
    build_simple_action: Callable[[str], ResolutionWorkbenchAction | None],
    continue_label: Callable[[], str],
    destination: SaveLocationView | None = None,
    turn_command_review: (
        Callable[[ResolutionWorkbenchAction], ExactCommandReview | None] | None
    ) = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
) -> ResolutionWorkbenchAction:
    """Navigate issues and stage choices without rendering the retained report.

    Left/Right changes the issue, Up/Down changes the compact row, number keys
    stage the matching choice, and the same rows remain operable with Enter.
    A command-bearing semantic turn receives one adjacent exact confirmation.
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
    pending_action: dict[str, ResolutionWorkbenchAction | None] = {"value": None}
    pending_review: dict[str, ExactCommandReview | None] = {"value": None}
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
    location_key_active = Condition(
        lambda: destination is not None and not destination_editing["value"]
    )

    def active_item() -> ResolutionItem | None:
        return items[item_index["value"]] if items else None

    def action_rows() -> tuple[tuple[str, str], ...]:
        capabilities = supplier().capabilities
        rows: list[tuple[str, str]] = []
        if "PRESERVE_ALL" in capabilities:
            rows.append(("P", "Preserve all"))
        if "DEFER" in capabilities:
            rows.append(("D", "Defer"))
        if destination is not None:
            rows.append(("L", f"Change {destination.label.lower()}"))
        rows.append(("A", continue_label()))
        return tuple(rows)

    def row_count() -> int:
        item = active_item()
        return (len(item.options) if item is not None else 0) + len(action_rows())

    def clamp_row() -> None:
        row_index["value"] = min(row_index["value"], max(row_count() - 1, 0))

    def selected_for(item: ResolutionItem) -> str | None:
        return selected_option(item.uid) or item.selected_option_uid

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
        if pending_review["value"] is not None:
            return [
                ("class:report-label", " RUN EXACT COMMAND\n"),
                (
                    "class:report-neutral",
                    safe_terminal_text(
                        render_exact_command_review(pending_review["value"])
                    )
                    + "\n\n",
                ),
                (
                    focused_control_style(focused=True, selected=True),
                    " › Enter · Run exact command",
                ),
            ]

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
        option_count = len(item.options) if item is not None else 0
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
            chosen_uid = selected_for(item)
            for index, option in enumerate(item.options):
                focused = row_index["value"] == index
                chosen = chosen_uid == option.uid
                marker = "✓" if chosen else " "
                prefix = f" {marker} [{index + 1}] "
                fragments.append(
                    (
                        focused_control_style(
                            focused=focused,
                            # In this deliberately sparse surface, blue is the
                            # visible arrow-key cursor while the check remains
                            # the complete staged-selection channel.
                            selected=focused or chosen,
                        ),
                        prefix + _choice_text(item, index) + "\n",
                    )
                )

        for offset, (key, label) in enumerate(action_rows()):
            focused = row_index["value"] == option_count + offset
            fragments.append(
                (
                    focused_control_style(focused=focused, selected=focused),
                    f"   [{key}] {safe_terminal_text(label)}\n",
                )
            )
        return fragments

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if pending_review["value"] is not None:
            return " Enter run · Esc/Backspace return · Q cancel"
        if destination_editing["value"]:
            return " Enter use exact name · Esc return · Ctrl-C cancel"
        location_hint = " · L location" if destination is not None else ""
        return (
            " ←/→ issue · ↑/↓ choice/action · Enter select · "
            f"1–9 choose · A continue · D defer{location_hint} · Esc save & close"
        )

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
        if not items or pending_review["value"] is not None:
            return
        item_index["value"] = (item_index["value"] + delta) % len(items)
        row_index["value"] = 0
        status["value"] = ""

    def move_row(delta: int) -> None:
        if pending_review["value"] is not None:
            return
        row_index["value"] = max(
            0,
            min(row_index["value"] + delta, max(row_count() - 1, 0)),
        )
        status["value"] = ""

    def finish_or_review(action: ResolutionWorkbenchAction | None) -> None:
        if action is None:
            status["value"] = "This action is not ready. Choose a required response."
            return
        review = (
            turn_command_review(action) if turn_command_review is not None else None
        )
        if review is None:
            app.exit(result=action)
            return
        pending_action["value"] = action
        pending_review["value"] = review
        status["value"] = ""

    def select_choice(index: int) -> None:
        item = active_item()
        if item is None or not 0 <= index < len(item.options):
            status["value"] = "That numbered choice is unavailable."
            return
        option = item.options[index]
        stage_option(item.uid, option.uid)
        row_index["value"] = index
        status["value"] = f"Selected · {safe_terminal_text(option.label)}"

    def activate() -> None:
        if pending_review["value"] is not None:
            action = pending_action["value"]
            if action is not None:
                app.exit(result=action)
            return
        item = active_item()
        option_count = len(item.options) if item is not None else 0
        if item is not None and row_index["value"] < option_count:
            select_choice(row_index["value"])
            return
        key, _label = action_rows()[row_index["value"] - option_count]
        if key == "A":
            finish_or_review(
                build_continue_action(item.uid if item is not None else None)
            )
        elif key == "P":
            finish_or_review(build_simple_action("PRESERVE_ALL"))
        else:
            finish_or_review(build_simple_action("DEFER"))

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

    for number in range(1, 10):
        key = str(number)

        @bindings.add(key, filter=decision_keys_active, eager=True)
        def _number(event, index: int = number - 1) -> None:
            if pending_review["value"] is None:
                select_choice(index)
            event.app.invalidate()

    @bind_case_insensitive_key(
        bindings,
        "a",
        filter=decision_keys_active,
        eager=True,
    )
    def _continue(event) -> None:
        if pending_review["value"] is None:
            item = active_item()
            finish_or_review(
                build_continue_action(item.uid if item is not None else None)
            )
        event.app.invalidate()

    @bind_case_insensitive_key(
        bindings,
        "p",
        filter=decision_keys_active,
        eager=True,
    )
    def _preserve(event) -> None:
        if (
            pending_review["value"] is None
            and "PRESERVE_ALL" in supplier().capabilities
        ):
            finish_or_review(build_simple_action("PRESERVE_ALL"))
        event.app.invalidate()

    @bind_case_insensitive_key(
        bindings,
        "d",
        filter=decision_keys_active,
        eager=True,
    )
    def _defer(event) -> None:
        if pending_review["value"] is None and "DEFER" in supplier().capabilities:
            finish_or_review(build_simple_action("DEFER"))
        event.app.invalidate()

    @bind_case_insensitive_key(
        bindings,
        "l",
        filter=location_key_active,
        eager=True,
    )
    def _location(event) -> None:
        open_destination()
        event.app.invalidate()

    def close_or_back(event) -> None:
        if pending_review["value"] is not None:
            pending_review["value"] = None
            pending_action["value"] = None
            clamp_row()
            event.app.invalidate()
            return
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
