"""Inline Source/Target selector for deterministic required resolutions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
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
    copy_plain_text,
    plain_text_from_fragments,
)
from memcommit.interfaces.tui.components.scrollable_pane import (
    build_scrollable_formatted_text_pane,
    scroll_wrapped_page,
)
from memcommit.interfaces.tui.core.keybindings import bind_case_insensitive_key
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.interfaces.tui.workbenches.resolution.model import (
    ResolutionItem,
    ResolutionOutcome,
    ResolutionWorkbenchSpec,
)
from memcommit.selection.model import SelectionOption
from memcommit.selection.state import FlatSelectionState
from memcommit.selection.tui import choice_marker, choice_visual_state


T = TypeVar("T")


def render_inline_resolution_item(
    item: ResolutionItem,
    state: FlatSelectionState,
    *,
    ordinal: int,
    focused: bool,
) -> list[tuple[str, str]]:
    """Render both complete values without shortening either Memory body."""

    fragments: list[tuple[str, str]] = [
        (
            "class:memcommit.control.focused" if focused else "",
            f"{'›' if focused else ' '} {ordinal} · {safe_terminal_text(item.label)} ",
        )
    ]
    for index, choice in enumerate(item.inline_choices):
        selected = choice.choice_uid == state.selected_uid
        cursor = choice.choice_uid == state.cursor_uid
        visual = choice_visual_state(
            cursor=cursor,
            selected=selected,
            focused=focused,
        )
        unavailable = not choice.selectable
        marker = "×" if unavailable else choice_marker(selected=selected)
        prefix = f"{marker} {safe_terminal_text(choice.label)} "
        content = f'"{safe_terminal_text(choice.content)}"'
        if unavailable:
            fragments.extend(
                [
                    ("class:loading-placeholder", prefix),
                    ("class:loading-placeholder", content),
                ]
            )
        elif visual.keyboard_target or selected:
            fragments.append((visual.content_style, prefix + content))
        else:
            fragments.extend(
                [
                    ("class:report-label", prefix),
                    (
                        "class:memory-object"
                        if choice.memory_content
                        else "class:report-neutral",
                        content,
                    ),
                ]
            )
        if index < len(item.inline_choices) - 1:
            fragments.append(("class:report-neutral", " ≠ "))
    fragments.append(("", "\n"))
    return fragments


def run_inline_resolution_workbench(
    spec: ResolutionWorkbenchSpec,
    *,
    apply_outcome: Callable[[ResolutionOutcome], T],
    receipt_text: Callable[[T], str],
    review_outcome: Callable[[ResolutionOutcome], ExactCommandReview] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    clipboard_writer: ClipboardWriter | None = None,
    require_tty: bool = True,
) -> T | None:
    """Stage complete inline choices, review once, and apply atomically."""

    if not spec.inline_choice_layout:
        raise ValueError("The inline Resolution shell requires inline layout.")
    if require_tty:
        require_interactive_terminal(
            spec.title,
            snapshot_hint="Use explicit noninteractive resolution flags outside a TTY.",
        )

    bindings = KeyBindings()
    item_count = len(spec.items)
    row_cursor = {"value": 0}
    # Conflict inspection and mutation actions are separate focus surfaces.
    # The action cursor starts on Apply so one Tab reaches the safe staged
    # default regardless of how many frozen conflicts precede it.
    action_cursor = {"value": 1}
    bulk_cursor = {"value": 0}
    focused_surface = {"value": "CONFLICTS"}
    selected = {
        item.uid: item.default_choice_uid
        for item in spec.items
        if item.default_choice_uid is not None
    }
    choice_states = {
        item.uid: FlatSelectionState(
            tuple(
                SelectionOption(choice.choice_uid, choice.label, choice.content)
                for choice in item.inline_choices
                if choice.selectable
            ),
            cursor_uid=item.default_choice_uid or "",
            selected_uid=item.default_choice_uid,
            allow_empty=False,
        )
        for item in spec.items
    }
    review_mode: dict[str, str | None] = {"value": None}
    result: dict[str, T | None] = {"value": None}
    status = {"value": ""}
    last_error: dict[str, Exception | None] = {"value": None}

    def uniform_bulk_uid() -> str | None:
        """Project a whole-set choice whenever every staged row agrees."""

        return next(
            (
                strategy.choice_uid
                for strategy in spec.bulk_strategies
                if all(selected[item.uid] == strategy.choice_uid for item in spec.items)
            ),
            None,
        )

    def decisions() -> ResolutionOutcome:
        values = tuple((item.uid, selected[item.uid]) for item in spec.items)
        return spec.validate_outcome(
            ResolutionOutcome(values, bulk_uid=uniform_bulk_uid())
        )

    def current_review() -> ExactCommandReview:
        outcome = decisions()
        if outcome.bulk_uid is not None:
            return next(
                strategy.review
                for strategy in spec.bulk_strategies
                if strategy.choice_uid == outcome.bulk_uid
            )
        if review_outcome is None:
            return spec.exact_review
        reviewed = review_outcome(outcome)
        if not isinstance(reviewed, ExactCommandReview):
            raise TypeError(
                "Resolution exact-review factory returned an invalid value."
            )
        return reviewed

    def render_bulk(*, focused: bool) -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = [
            (
                "class:memcommit.control.focused" if focused else "",
                f"{'›' if focused else ' '} BULK DECISION · ",
            )
        ]
        uniform_uid = uniform_bulk_uid()
        for index, strategy in enumerate(spec.bulk_strategies):
            cursor = index == bulk_cursor["value"]
            selected_as_whole = strategy.choice_uid == uniform_uid
            style = focused_control_style(
                focused=focused and cursor,
                # This is a derived summary of every checked row, not hidden
                # bulk state. Mixed row decisions deliberately light neither.
                selected=selected_as_whole,
            )
            fragments.append(
                (
                    style,
                    f"{'✓ ' if selected_as_whole else '  '}"
                    f"{safe_terminal_text(strategy.label)}",
                )
            )
            if index < len(spec.bulk_strategies) - 1:
                fragments.append(("class:report-neutral", " / "))
        fragments.append(("", "\n"))
        return fragments

    def render_normal() -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = []
        for index, item in enumerate(spec.items):
            fragments.extend(
                render_inline_resolution_item(
                    item,
                    choice_states[item.uid],
                    ordinal=index + 1,
                    focused=(
                        focused_surface["value"] == "CONFLICTS"
                        and row_cursor["value"] == index
                    ),
                )
            )
        return fragments

    def render_actions() -> list[tuple[str, str]]:
        focused = focused_surface["value"] == "CONTROLS"
        if result["value"] is not None:
            return [
                (
                    focused_control_style(focused=focused, selected=True),
                    f"{'›' if focused else ' '} CLOSE",
                )
            ]
        if review_mode["value"] is not None:
            return [
                (
                    focused_control_style(focused=focused, selected=True),
                    f"{'›' if focused else ' '} APPLY EXACT WHOLE SET",
                )
            ]
        fragments = render_bulk(focused=focused and action_cursor["value"] == 0)
        apply_focused = focused and action_cursor["value"] == 1
        fragments.append(
            (
                focused_control_style(focused=apply_focused, selected=True),
                f"{'›' if apply_focused else ' '} APPLY · READY",
            )
        )
        return fragments

    def render_main() -> list[tuple[str, str]]:
        if result["value"] is not None:
            return [
                ("class:loading-complete", "MERGE RECORDED\n"),
                (
                    "class:report-neutral",
                    safe_terminal_text(receipt_text(result["value"])),
                ),
            ]
        if review_mode["value"] is not None:
            return [
                ("class:report-label", "APPLY CONFIRMATION · EXACT WHOLE SET\n"),
                ("class:report-neutral", render_exact_command_review(current_review())),
            ]
        return render_normal()

    main_pane = build_scrollable_formatted_text_pane(
        "INLINE RESOLUTION",
        render_main(),
        height=Dimension(min=14, weight=1),
    )
    main_control = main_pane.text_area.control
    main_window = main_pane.text_area.window
    main_frame = build_focused_frame(
        main_window,
        title=lambda: (
            "RECEIPT"
            if result["value"] is not None
            else "REVIEW"
            if review_mode["value"] is not None
            else "CONFLICTS"
        ),
        is_focused=lambda: get_app().layout.has_focus(main_control),
        height=Dimension(min=14, weight=1),
    )
    actions_control = FormattedTextControl(render_actions, focusable=True)
    actions_window = Window(
        actions_control,
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    actions_frame = build_focused_frame(
        actions_window,
        title="CONTROLS",
        is_focused=lambda: get_app().layout.has_focus(actions_control),
        height=Dimension.exact(4),
    )
    header = Window(
        FormattedTextControl(
            f" {safe_terminal_text(spec.title)}\n {safe_terminal_text(spec.subtitle)}"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if result["value"] is not None:
            return (
                " Enter/Esc/Q close · durable receipt shown"
                if get_app().layout.has_focus(actions_control)
                else " Tab Controls to close · PgUp/PgDn receipt · Esc/Q close"
            )
        if review_mode["value"] is not None:
            return (
                " Enter apply exact command · Esc/Backspace return"
                if get_app().layout.has_focus(actions_control)
                else " Tab Controls to apply · PgUp/PgDn review · Esc/Backspace return"
            )
        return (
            " Tab conflicts/controls · ↑/↓ row/control · ←/→ Source/Target "
            "· Enter choose/review · PgUp/PgDn scroll · y row · Y all · Esc cancel"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(main_frame),
        TuiRegion(actions_frame),
        TuiRegion(footer),
    )
    app: Application[T | None] = Application(
        layout=Layout(root, focused_element=main_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def refresh_main(*, anchor: str = "focused") -> None:
        """Refresh styling while retaining a real cursor-backed read viewport."""

        main_pane.set_formatted_text(
            render_main(),
            anchor="start" if anchor == "start" else "preserve",
        )
        if anchor != "focused":
            return
        # The visible pointer is also the read-buffer anchor. This lets the
        # shared wrapped-page navigation move through a Memory taller than the
        # terminal while Up/Down can still return to a deterministic row.
        pointer = main_pane.text_area.buffer.text.find("› ")
        if pointer >= 0:
            main_pane.text_area.buffer.cursor_position = pointer

    def focus_conflicts() -> None:
        focused_surface["value"] = "CONFLICTS"
        refresh_main()

    def focus_actions() -> None:
        focused_surface["value"] = "CONTROLS"
        refresh_main(anchor="preserve")

    def enter_conflicts_from_vertical(delta: int) -> None:
        row_cursor["value"] = 0 if delta > 0 else item_count - 1
        refresh_main()

    def enter_actions_from_vertical(delta: int) -> None:
        action_cursor["value"] = 0 if delta > 0 else 1

    def move_conflicts(_event, delta: int) -> SurfaceMoveResult:
        if result["value"] is not None or review_mode["value"] is not None:
            return "BOUNDARY"
        before = row_cursor["value"]
        row_cursor["value"] = max(0, min(before + delta, item_count - 1))
        if before != row_cursor["value"]:
            refresh_main()
        return "MOVED" if before != row_cursor["value"] else "BOUNDARY"

    def move_actions(_event, delta: int) -> SurfaceMoveResult:
        if result["value"] is not None or review_mode["value"] is not None:
            return "BOUNDARY"
        before = action_cursor["value"]
        action_cursor["value"] = max(0, min(before + delta, 1))
        return "MOVED" if before != action_cursor["value"] else "BOUNDARY"

    def apply_review(_event) -> SurfaceActionResult:
        try:
            completed = apply_outcome(decisions())
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            last_error["value"] = error
            status["value"] = f"Apply failed · {error}"
            return "HANDLED"
        result["value"] = completed
        last_error["value"] = None
        status["value"] = ""
        refresh_main(anchor="start")
        return "HANDLED"

    def activate_conflict(event) -> SurfaceActionResult:
        if result["value"] is not None or review_mode["value"] is not None:
            # Review and receipt remain independently scrollable evidence;
            # their mutation/close affordance belongs only to Controls.
            return "HANDLED"
        row = row_cursor["value"]
        if row < item_count - 1:
            row_cursor["value"] = row + 1
            refresh_main()
            return "HANDLED"
        action_cursor["value"] = 0
        focus_actions()
        event.app.layout.focus(actions_control)
        return "HANDLED"

    def activate_actions(event) -> SurfaceActionResult:
        if result["value"] is not None:
            event.app.exit(result=result["value"])
            return "HANDLED"
        if review_mode["value"] is not None:
            return apply_review(event)
        if action_cursor["value"] == 0:
            strategy = spec.bulk_strategies[bulk_cursor["value"]]
            for item in spec.items:
                state = choice_states[item.uid]
                state.set_selected(strategy.choice_uid)
                state.cursor_uid = strategy.choice_uid
                selected[item.uid] = strategy.choice_uid
            action_cursor["value"] = 1
            refresh_main()
            return "HANDLED"
        review_mode["value"] = uniform_bulk_uid() or "INDIVIDUAL"
        refresh_main(anchor="start")
        return "HANDLED"

    focus = SurfaceFocusController(
        (
            FocusSurface(
                "CONFLICTS",
                main_control,
                move_vertical=move_conflicts,
                activate=activate_conflict,
                on_focus=focus_conflicts,
                on_vertical_enter=enter_conflicts_from_vertical,
            ),
            FocusSurface(
                "CONTROLS",
                actions_control,
                move_vertical=move_actions,
                activate=activate_actions,
                on_focus=focus_actions,
                on_vertical_enter=enter_actions_from_vertical,
            ),
        )
    )
    bind_surface_navigation(bindings, focus)

    def move_horizontal(delta: int) -> None:
        if result["value"] is not None or review_mode["value"] is not None:
            return
        if focused_surface["value"] == "CONFLICTS":
            item = spec.items[row_cursor["value"]]
            state = choice_states[item.uid]
            if state.move(delta):
                choice_uid = state.select_cursor(toggle=False)
                assert choice_uid is not None
                selected[item.uid] = choice_uid
                refresh_main()
            return
        if action_cursor["value"] == 0 and spec.bulk_strategies:
            before = bulk_cursor["value"]
            bulk_cursor["value"] = max(
                0,
                min(
                    bulk_cursor["value"] + delta,
                    len(spec.bulk_strategies) - 1,
                ),
            )
            if bulk_cursor["value"] != before:
                get_app().invalidate()

    resolution_focus = has_focus(main_control) | has_focus(actions_control)

    @bindings.add("left", filter=resolution_focus, eager=True)
    def _left(event) -> None:
        move_horizontal(-1)
        event.app.invalidate()

    @bindings.add("right", filter=resolution_focus, eager=True)
    def _right(event) -> None:
        move_horizontal(1)
        event.app.invalidate()

    @bindings.add("pageup", filter=has_focus(main_control), eager=True)
    def _page_up(event) -> None:
        scroll_wrapped_page(event, direction=-1)

    @bindings.add("pagedown", filter=has_focus(main_control), eager=True)
    def _page_down(event) -> None:
        scroll_wrapped_page(event, direction=1)

    def copy_conflicts(event, *, whole: bool) -> None:
        if result["value"] is not None or review_mode["value"] is not None:
            fragments = render_main()
            label = "current review or receipt"
        elif whole or focused_surface["value"] == "CONTROLS":
            fragments = [
                fragment
                for index, item in enumerate(spec.items)
                for fragment in render_inline_resolution_item(
                    item,
                    choice_states[item.uid],
                    ordinal=index + 1,
                    focused=False,
                )
            ]
            label = "all conflict rows"
        else:
            index = row_cursor["value"]
            item = spec.items[index]
            fragments = render_inline_resolution_item(
                item,
                choice_states[item.uid],
                ordinal=index + 1,
                focused=False,
            )
            label = "focused conflict row"
        copied = copy_plain_text(
            plain_text_from_fragments(fragments, whole_document=True),
            success_message=label,
            writer=clipboard_writer,
        )
        status["value"] = copied.message
        event.app.invalidate()

    @bindings.add("y", filter=resolution_focus, eager=True)
    def _copy_focused(event) -> None:
        copy_conflicts(event, whole=False)

    @bindings.add("Y", filter=resolution_focus, eager=True)
    def _copy_complete(event) -> None:
        copy_conflicts(event, whole=True)

    def close(event) -> None:
        event.app.exit(result=result["value"])

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        if result["value"] is not None:
            close(event)
        elif review_mode["value"] is not None:
            review_mode["value"] = None
            status["value"] = ""
            refresh_main()
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


__all__ = ["render_inline_resolution_item", "run_inline_resolution_workbench"]
