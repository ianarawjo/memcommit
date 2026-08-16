"""Shared Viewer/Responses/Items/To-Do shell for deterministic resolutions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition
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

from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
    render_exact_command_review,
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
from memcommit.interfaces.tui.components.plain_text_clipboard import (
    ClipboardWriter,
    PlainTextClipboardReceipt,
    copy_plain_text,
)
from memcommit.interfaces.tui.core.keybindings import bind_case_insensitive_key
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerController,
    SemanticViewerDocument,
)
from memcommit.interfaces.tui.workbenches.resolution.model import (
    ResolutionOutcome,
    ResolutionWorkbenchSpec,
)
from memcommit.selection.model import SelectionOption
from memcommit.selection.state import FlatSelectionState
from memcommit.selection.tui import render_vertical_choice_rows
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation


T = TypeVar("T")


def _document_text(document: SemanticViewerDocument) -> str:
    return "".join(
        text
        for section in document.sections
        for style, text in section.block.fragments
        if style != "[SetCursorPosition]"
    ).strip()


def _focused_text(
    document: SemanticViewerDocument,
    controller: SemanticViewerController,
) -> str:
    current = controller.current(document)
    if current is None:
        return ""
    section = next(section for section in document.sections if section.uid == current.uid)
    return "".join(
        text
        for style, text in section.block.fragments
        if style != "[SetCursorPosition]"
    ).strip()


def run_resolution_workbench(
    spec: ResolutionWorkbenchSpec,
    *,
    apply_outcome: Callable[[ResolutionOutcome], T],
    receipt_text: Callable[[T], str],
    review_outcome: Callable[[ResolutionOutcome], ExactCommandReview] | None = None,
    clipboard_writer: ClipboardWriter | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> T | None:
    """Collect every required choice, review the whole set, then apply once."""

    if not isinstance(spec, ResolutionWorkbenchSpec):
        raise TypeError("Resolution workbench requires a typed specification.")
    if require_tty:
        require_interactive_terminal(
            spec.title,
            snapshot_hint="Use explicit noninteractive resolution flags outside a TTY.",
        )

    bindings = KeyBindings()
    controller = SemanticViewerController(SessionWorkbenchNavigation())
    opened_uid: dict[str, str | None] = {"value": None}
    item_cursor = {"value": 0}
    selected: dict[str, str] = {}
    choice_states = {
        item.uid: FlatSelectionState(
            tuple(
                SelectionOption(choice.uid, choice.label, choice.description)
                for choice in item.choices
            ),
            cursor_uid=item.choices[0].uid,
            selected_uid=None,
            allow_empty=True,
        )
        for item in spec.items
    }
    review_mode: dict[str, str | None] = {"value": None}
    review_return_uid: dict[str, str | None] = {"value": None}
    result: dict[str, T | None] = {"value": None}
    status: dict[str, str] = {"value": ""}
    last_error: dict[str, Exception | None] = {"value": None}

    def opened_item():
        uid = opened_uid["value"]
        return next((item for item in spec.items if item.uid == uid), None)

    def document() -> SemanticViewerDocument:
        item = opened_item()
        return spec.report if item is None else item.detail

    viewer_control = FormattedTextControl(
        lambda: controller.render(
            document(),
            viewer_focused=get_app().layout.has_focus(viewer_control),
        ),
        focusable=True,
        show_cursor=False,
    )
    viewer_frame = build_focused_frame(
        Window(
            viewer_control,
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        ),
        title=lambda: (
            "VIEWER · COMPLETE REPORT"
            if opened_item() is None
            else spec.detail_title
        ),
        is_focused=lambda: get_app().layout.has_focus(viewer_control),
        height=Dimension(min=14, weight=1),
    )

    def render_responses():
        item = opened_item()
        if item is None:
            return []
        state = choice_states[item.uid]
        return [
            ("class:report-label", f"QUESTION · {safe_terminal_text(item.label)}\n\n"),
            *render_vertical_choice_rows(
                state,
                focused=get_app().layout.has_focus(responses_control),
                content_width=max(42, get_app().output.get_size().columns - 10),
                numbered=True,
            ),
        ]

    responses_control = FormattedTextControl(
        render_responses,
        focusable=True,
        show_cursor=False,
    )
    responses_frame = ConditionalContainer(
        build_focused_frame(
            Window(responses_control, wrap_lines=True),
            title=spec.responses_title,
            is_focused=lambda: get_app().layout.has_focus(responses_control),
            height=Dimension(min=8, max=13),
        ),
        filter=Condition(lambda: opened_item() is not None),
    )

    def render_items():
        focused = get_app().layout.has_focus(items_control)
        fragments: list[tuple[str, str]] = [
            (
                "class:report-label",
                f"REQUIRED {len(spec.items)} · "
                f"ANSWERED {len(selected)} · "
                f"REMAINING {len(spec.items) - len(selected)}\n",
            )
        ]
        for index, item in enumerate(spec.items):
            cursor = index == item_cursor["value"]
            checked = item.uid in selected
            style = focused_control_style(
                focused=focused and cursor,
                selected=checked,
            )
            fragments.append(
                (
                    style,
                    f"{'✓' if checked else '·'} {index + 1}. "
                    f"{safe_terminal_text(item.classification)} · "
                    f"{safe_terminal_text(item.label)}\n",
                )
            )
            if focused and cursor:
                fragments.append(("[SetCursorPosition]", ""))
        return fragments

    items_control = FormattedTextControl(
        render_items,
        focusable=True,
        show_cursor=False,
    )
    items_frame = build_focused_frame(
        Window(items_control, wrap_lines=True),
        title=spec.items_title,
        is_focused=lambda: get_app().layout.has_focus(items_control),
        height=Dimension(min=7, max=14),
    )

    def current_review():
        mode = review_mode["value"]
        if mode == "INDIVIDUAL" and review_outcome is not None:
            reviewed = review_outcome(decisions())
            if not isinstance(reviewed, ExactCommandReview):
                raise TypeError("Resolution exact-review factory returned an invalid value.")
            return reviewed
        if mode is None or mode == "INDIVIDUAL":
            return spec.exact_review
        return next(
            strategy.review
            for strategy in spec.bulk_strategies
            if strategy.choice_uid == mode
        )

    def render_todo():
        focused = get_app().layout.has_focus(todo_control)
        cursor = [("[SetCursorPosition]", "")] if focused else []
        if result["value"] is not None:
            return [
                ("class:loading-complete", "STATUS · SUCCESS\n"),
                ("class:report-neutral", safe_terminal_text(receipt_text(result["value"]))),
                ("", "\n\n"),
                *cursor,
                (focused_control_style(focused=focused), "[ PRESS ENTER TO CLOSE ]"),
            ]
        if review_mode["value"] is not None:
            mode = review_mode["value"]
            heading = (
                "FINAL REVIEW · ITEM-BY-ITEM DECISIONS"
                if mode == "INDIVIDUAL"
                else "BULK WHOLE-SET REVIEW · FUSED APPROVAL"
            )
            return [
                ("class:report-label", heading + "\n"),
                ("class:report-neutral", render_exact_command_review(current_review())),
                ("", "\n\n"),
                *cursor,
                (
                    focused_control_style(focused=focused),
                    "[ PRESS ENTER TO APPLY THIS EXACT WHOLE SET ]",
                ),
            ]
        unresolved = next((item for item in spec.items if item.uid not in selected), None)
        if unresolved is not None:
            text = (
                f"OPEN FIRST UNRESOLVED · {safe_terminal_text(unresolved.label)}\n"
                "Enter opens this required item. Apply stays unavailable."
            )
        else:
            text = (
                "REVIEW AND APPLY\n"
                "Enter opens the exact whole-set final review."
            )
        bulk = "".join(
            f" · {strategy.key.upper()} {safe_terminal_text(strategy.label)}"
            for strategy in spec.bulk_strategies
        )
        return [
            ("class:report-neutral", text + "\n"),
            *cursor,
            (focused_control_style(focused=focused), "[ PRESS ENTER ]"),
            ("class:report-neutral", bulk),
        ]

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · ONE NEXT ACTION",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        # Final approval must show the command as well as its complete effect
        # boundary. Temporarily reclaim the Responses space instead of letting
        # the bottom cursor scroll the command out of the review viewport.
        height=lambda: (
            Dimension(min=20, max=24, weight=3)
            if review_mode["value"] is not None
            else Dimension(min=9, max=18)
        ),
    )

    header = Window(
        FormattedTextControl(
            f" {safe_terminal_text(spec.title)}\n {safe_terminal_text(spec.subtitle)}"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer():
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if result["value"] is not None:
            return " Enter/Esc/Q close · durable receipt shown"
        if review_mode["value"] is not None:
            return " Enter applies the displayed exact command · Esc/Backspace returns"
        return (
            " ↑/↓ move · Enter open/select · Tab frames · Esc/Backspace back "
            "· y focused · Y complete · Q close"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(viewer_frame),
        TuiRegion(responses_frame),
        TuiRegion(items_frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[T | None] = Application(
        layout=Layout(root, focused_element=viewer_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_viewer(_event, delta: int) -> SurfaceMoveResult:
        before = controller.current(document())
        after = controller.move(document(), delta)
        return "MOVED" if before != after else "BOUNDARY"

    def move_responses(_event, delta: int) -> SurfaceMoveResult:
        item = opened_item()
        if item is None:
            return "BOUNDARY"
        return "MOVED" if choice_states[item.uid].move(delta) else "BOUNDARY"

    def choose_response(_event) -> SurfaceActionResult:
        item = opened_item()
        if item is None:
            return "IGNORED"
        state = choice_states[item.uid]
        choice_uid = state.select_cursor(toggle=True)
        if choice_uid is None:
            selected.pop(item.uid, None)
        else:
            selected[item.uid] = choice_uid
        review_mode["value"] = None
        return "HANDLED"

    def move_items(_event, delta: int) -> SurfaceMoveResult:
        before = item_cursor["value"]
        item_cursor["value"] = max(
            0,
            min(before + delta, len(spec.items) - 1),
        )
        return "MOVED" if before != item_cursor["value"] else "BOUNDARY"

    def open_item(item_uid: str, event) -> None:
        opened_uid["value"] = item_uid
        state = choice_states[item_uid]
        state.set_selected(selected.get(item_uid))
        state.reset_cursor_to_selection()
        controller.navigation.section_uid = None
        event.app.layout.focus(viewer_control)

    def activate_item(event) -> SurfaceActionResult:
        open_item(spec.items[item_cursor["value"]].uid, event)
        return "HANDLED"

    def decisions(*, bulk_uid: str | None = None) -> ResolutionOutcome:
        values = (
            tuple((item.uid, bulk_uid) for item in spec.items)
            if bulk_uid is not None
            else tuple((item.uid, selected[item.uid]) for item in spec.items)
        )
        # Presentation never becomes mutation authority. Re-enter the same
        # revision-bound case validator used by CLI/Python before review or
        # Apply so a UI projection cannot widen item or choice capabilities.
        return spec.validate_outcome(ResolutionOutcome(values, bulk_uid=bulk_uid))

    def apply_review(event) -> SurfaceActionResult:
        mode = review_mode["value"]
        assert mode is not None
        outcome = decisions(bulk_uid=None if mode == "INDIVIDUAL" else mode)
        try:
            completed = apply_outcome(outcome)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            last_error["value"] = error
            status["value"] = f"Apply failed · {error}"
            return "HANDLED"
        result["value"] = completed
        last_error["value"] = None
        status["value"] = ""
        return "HANDLED"

    def activate_todo(event) -> SurfaceActionResult:
        if result["value"] is not None:
            event.app.exit(result=result["value"])
            return "HANDLED"
        if review_mode["value"] is not None:
            return apply_review(event)
        unresolved = next((item for item in spec.items if item.uid not in selected), None)
        if unresolved is not None:
            open_item(unresolved.uid, event)
            return "HANDLED"
        review_return_uid["value"] = opened_uid["value"]
        opened_uid["value"] = None
        controller.navigation.section_uid = None
        review_mode["value"] = "INDIVIDUAL"
        return "HANDLED"

    def surfaces():
        values = [
            FocusSurface("VIEWER", viewer_control, move_vertical=move_viewer),
        ]
        if opened_item() is not None:
            values.append(
                FocusSurface(
                    "RESPONSES",
                    responses_control,
                    move_vertical=move_responses,
                    activate=choose_response,
                    on_focus=lambda: choice_states[opened_item().uid].reset_cursor_to_selection(),  # type: ignore[union-attr]
                )
            )
        values.extend(
            (
                FocusSurface(
                    "ITEMS",
                    items_control,
                    move_vertical=move_items,
                    activate=activate_item,
                ),
                FocusSurface(
                    "TO_DO",
                    todo_control,
                    move_vertical=lambda _event, _delta: "BOUNDARY",
                    activate=activate_todo,
                ),
            )
        )
        return tuple(values)

    focus = SurfaceFocusController(surfaces)
    bind_surface_navigation(bindings, focus)

    @bindings.add("home", eager=True)
    def _home(event) -> None:
        if event.app.layout.has_focus(viewer_control):
            controller.home(document())
            event.app.invalidate()

    @bindings.add("end", eager=True)
    def _end(event) -> None:
        if event.app.layout.has_focus(viewer_control):
            controller.end(document())
            event.app.invalidate()

    def copy_viewer(event, *, whole: bool) -> None:
        if not event.app.layout.has_focus(viewer_control):
            return
        text = _document_text(document()) if whole else _focused_text(document(), controller)
        copied: PlainTextClipboardReceipt = copy_plain_text(
            text,
            success_message="complete current document" if whole else "focused section",
            writer=clipboard_writer,
        )
        status["value"] = copied.message
        event.app.invalidate()

    @bindings.add("y", eager=True)
    def _copy_focused(event) -> None:
        copy_viewer(event, whole=False)

    @bindings.add("Y", eager=True)
    def _copy_complete(event) -> None:
        copy_viewer(event, whole=True)

    for strategy in spec.bulk_strategies:

        @bind_case_insensitive_key(bindings, strategy.key, eager=True)
        def _bulk(event, strategy=strategy) -> None:
            if not event.app.layout.has_focus(todo_control) or result["value"] is not None:
                return
            review_return_uid["value"] = opened_uid["value"]
            opened_uid["value"] = None
            controller.navigation.section_uid = None
            review_mode["value"] = strategy.choice_uid
            event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=result["value"])

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        if result["value"] is not None:
            close(event)
        elif review_mode["value"] is not None:
            review_mode["value"] = None
            opened_uid["value"] = review_return_uid["value"]
            review_return_uid["value"] = None
            controller.navigation.section_uid = None
        elif opened_item() is not None:
            opened_uid["value"] = None
            controller.navigation.section_uid = None
            event.app.layout.focus(viewer_control)
        else:
            close(event)
        event.app.invalidate()

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bind_case_insensitive_key(bindings, "q", eager=True)
    def _close(event) -> None:
        close(event)

    try:
        outcome = app.run()
    except (EOFError, KeyboardInterrupt):
        outcome = result["value"]
    if outcome is None and last_error["value"] is not None:
        raise RuntimeError(f"Resolution application failed: {last_error['value']}")
    return outcome
