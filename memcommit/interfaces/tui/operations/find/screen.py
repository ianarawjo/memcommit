"""Interactive provider-free Find setup and result Viewer."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down, scroll_page_up
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.clipboard import ClipboardError
from memcommit.context_targeting.tui.range_selection import ContextRangeSelectionState
from memcommit.context_targeting.tui.reach import render_context_reach
from memcommit.context_targeting.tui.selection import render_context_target_mode
from memcommit.interfaces.cli.find import (
    project_literal_find_match,
    render_literal_find_result,
)
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.operations.find.model import (
    LiteralFindTuiOutcome,
    LiteralFindTuiSetup,
)
from memcommit.literal_find_application import LiteralFindRequest, LiteralFindResult


LiteralFindRunner = Callable[[LiteralFindRequest], LiteralFindResult]


def _choice(*values: tuple[str, str], selected: str) -> HorizontalChoiceState:
    return HorizontalChoiceState(
        tuple(HorizontalChoiceOption(uid, label) for uid, label in values),
        selected_uid=selected,
    )


def _render_match_content(result: LiteralFindResult, selected_index: int):
    if not result.matches:
        return [("", "(no matching Memories)")]
    fragments: list[tuple[str, str]] = []
    for index, match in enumerate(result.matches):
        source = match.source
        focused = index == selected_index
        if focused:
            fragments.append(("[SetCursorPosition]", ""))
        heading_style = (
            "class:detail-card.focused" if focused else "class:detail-card"
        )
        fragments.append(
            (
                heading_style,
                f"[{index + 1}/{len(result.matches)}] "
                f"{safe_terminal_text(source.context_name)} · "
                f"{source.kind.upper()} · {source.item_uid[:8]}\n",
            )
        )
        fragments.append(
            (
                "class:report-neutral",
                "SPANS · "
                + ", ".join(f"{span.start}:{span.end}" for span in match.spans)
                + "\n",
            )
        )
        fragments.append(("class:memory-object", safe_terminal_text(source.content)))
        if index < len(result.matches) - 1:
            fragments.append(("", "\n\n"))
    return fragments


def run_literal_find_tui(
    request: LiteralFindRequest | None,
    *,
    setup: LiteralFindTuiSetup,
    execute: LiteralFindRunner,
    clipboard_writer: Callable[[str], None] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> LiteralFindTuiOutcome | None:
    """Edit one exact request, run explicitly, and inspect complete matches."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Find",
            snapshot_hint='Pass a pattern, for example: mem find "parking".',
        )
    if not isinstance(setup, LiteralFindTuiSetup):
        raise TypeError("Find TUI requires a LiteralFindTuiSetup.")
    if request is not None and not isinstance(request, LiteralFindRequest):
        raise TypeError("Find TUI request must be a LiteralFindRequest or None.")
    if not callable(execute):
        raise TypeError("Find TUI requires an execution callback.")

    initial_targets = (
        setup.initial_targets if request is None else request.target_names
    )
    if any(name not in setup.names for name in initial_targets):
        raise ValueError("Find TUI request targets left the frozen catalog.")
    target_state = ContextRangeSelectionState.create(
        setup.names,
        current_name=setup.current_name,
        initial_target=initial_targets[0],
        multiple=True,
        include_descendants=(False if request is None else request.include_descendants),
    )
    target_state.selection.replace(initial_targets)
    embed_choice = _choice(
        ("EXCLUDE", "EXCLUDE EMBEDS"),
        ("FOLLOW", "FOLLOW EMBEDS"),
        selected=("FOLLOW" if request is not None and request.follow_embeds else "EXCLUDE"),
    )
    mode_choice = _choice(
        ("LITERAL", "LITERAL"),
        ("REGEX", "REGEX"),
        selected=("LITERAL" if request is None else request.mode),
    )
    case_choice = _choice(
        ("SENSITIVE", "CASE SENSITIVE"),
        ("IGNORE", "IGNORE CASE"),
        selected=("IGNORE" if request is not None and request.ignore_case else "SENSITIVE"),
    )
    annotations = dict(setup.annotations)
    result: LiteralFindResult | None = None
    result_index = 0
    scope_row = 0
    status = "READY · ENTER A PATTERN"

    bindings = KeyBindings()
    pattern_area = TextArea(
        text="" if request is None else request.pattern,
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        name="literal-find-pattern",
    )

    def clear_result() -> None:
        nonlocal result, result_index, status
        result = None
        result_index = 0
        status = "READY · REQUEST CHANGED"

    pattern_area.buffer.on_text_changed += lambda _buffer: clear_result()

    def render_targets():
        return target_state.render_rows(
            focused=app.layout.has_focus(target_control),
            annotations=annotations,
        )

    target_control = FormattedTextControl(render_targets, focusable=True)
    target_window = Window(
        target_control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def render_scope():
        focused = app.layout.has_focus(scope_control)
        fragments = render_context_target_mode(
            target_state.target_mode,
            focused=focused and scope_row == 0,
        )
        fragments.append(("", "\n"))
        fragments.extend(
            render_context_reach(
                target_state.reach,
                title="LEXICAL RANGE",
                focused=focused and scope_row == 1,
            )
        )
        for row, title, choice in (
            (2, "EMBEDDED CONTEXTS", embed_choice),
            (3, "MATCH", mode_choice),
            (4, "CASE", case_choice),
        ):
            fragments.append(("", "\n"))
            fragments.extend(
                render_horizontal_choice(
                    choice,
                    title=title,
                    focused=focused and scope_row == row,
                )
            )
        return fragments

    scope_control = FormattedTextControl(render_scope, focusable=True)

    def render_results():
        if result is None:
            return [("", "Enter a pattern to run provider-free Find.")]
        return _render_match_content(result, result_index)

    results_control = FormattedTextControl(render_results, focusable=True)
    results_window = Window(
        results_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
        always_hide_cursor=True,
    )

    def execute_request(_event=None):
        nonlocal result, result_index, status
        pattern = pattern_area.text
        targets = target_state.effective_names
        if not pattern:
            status = "PATTERN REQUIRED"
            app.layout.focus(pattern_area)
            return "HANDLED"
        if not targets:
            status = "SELECT AT LEAST ONE READABLE CONTEXT"
            app.layout.focus(target_control)
            return "HANDLED"
        try:
            candidate = LiteralFindRequest(
                pattern=pattern,
                target_names=targets,
                include_descendants=False,
                # effective_names already projects the visible lexical range;
                # freezing it prevents an unchecked child from being re-added.
                follow_embeds=embed_choice.selected_uid == "FOLLOW",
                mode=mode_choice.selected_uid,
                ignore_case=case_choice.selected_uid == "IGNORE",
            )
            result = execute(candidate)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status = safe_terminal_text(str(error)).upper()
            return "HANDLED"
        result_index = 0
        status = (
            f"COMPLETE · {len(result.matches)} MEMORIES"
            f" · {result.occurrence_count} OCCURRENCES"
        )
        app.layout.focus(results_control)
        return "HANDLED"

    def move_target(_event, delta: int):
        return "MOVED" if target_state.move_cursor(delta) else "BOUNDARY"

    def toggle_target(_event):
        if target_state.toggle_cursor():
            clear_result()
        return "HANDLED"

    def enter_target(delta: int) -> None:
        target_state.enter_from_boundary(delta)

    def move_scope(_event, delta: int):
        nonlocal scope_row
        candidate = scope_row + delta
        if not 0 <= candidate <= 4:
            return "BOUNDARY"
        scope_row = candidate
        return "MOVED"

    def enter_scope(delta: int) -> None:
        nonlocal scope_row
        scope_row = 0 if delta > 0 else 4

    def move_results(_event, delta: int):
        nonlocal result_index
        if result is None or not result.matches:
            return "BOUNDARY"
        candidate = result_index + delta
        if not 0 <= candidate < len(result.matches):
            return "BOUNDARY"
        result_index = candidate
        return "MOVED"

    surfaces = SurfaceFocusController(
        (
            FocusSurface("pattern", pattern_area, activate=execute_request),
            FocusSurface(
                "targets",
                target_control,
                move_vertical=move_target,
                activate=toggle_target,
                on_vertical_enter=enter_target,
            ),
            FocusSurface(
                "scope",
                scope_control,
                move_vertical=move_scope,
                activate=execute_request,
                on_vertical_enter=enter_scope,
            ),
            FocusSurface(
                "results",
                results_control,
                move_vertical=move_results,
            ),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("left", filter=has_focus(target_control), eager=True)
    def _collapse_target(event) -> None:
        target_state.collapse_cursor()
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(target_control), eager=True)
    def _expand_target(event) -> None:
        target_state.expand_cursor()
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(scope_control), eager=True)
    def _scope_left(event) -> None:
        _move_scope_choice(-1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(scope_control), eager=True)
    def _scope_right(event) -> None:
        _move_scope_choice(1)
        event.app.invalidate()

    def _move_scope_choice(delta: int) -> None:
        changed = False
        if scope_row == 0:
            control_changed, selection_changed = target_state.move_target_mode(delta)
            changed = control_changed or selection_changed
        elif scope_row == 1:
            changed = target_state.move_reach(delta)
        elif scope_row == 2:
            changed = embed_choice.move(delta)
        elif scope_row == 3:
            changed = mode_choice.move(delta)
        else:
            changed = case_choice.move(delta)
        if changed:
            clear_result()

    @bindings.add("pageup", filter=has_focus(results_control), eager=True)
    def _results_page_up(event) -> None:
        scroll_page_up(event)

    @bindings.add("pagedown", filter=has_focus(results_control), eager=True)
    def _results_page_down(event) -> None:
        scroll_page_down(event)

    def copy_result(*, whole: bool) -> None:
        nonlocal status
        if result is None or clipboard_writer is None:
            status = "NOTHING TO COPY"
            return
        text = (
            render_literal_find_result(result)
            if whole or not result.matches
            else project_literal_find_match(result.matches[result_index])
        )
        try:
            clipboard_writer(text)
        except ClipboardError as error:
            status = safe_terminal_text(str(error)).upper()
            return
        status = "COPIED RESULT SET" if whole else "COPIED FOCUSED MATCH"

    @bindings.add("y", filter=has_focus(results_control), eager=True)
    def _copy_focused(event) -> None:
        copy_result(whole=False)
        event.app.invalidate()

    @bindings.add("Y", filter=has_focus(results_control), eager=True)
    def _copy_all(event) -> None:
        copy_result(whole=True)
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(
            result=None if result is None else LiteralFindTuiOutcome(result)
        )

    @bindings.add("q", filter=~has_focus(pattern_area), eager=True)
    def _close_q(event) -> None:
        event.app.exit(
            result=None if result is None else LiteralFindTuiOutcome(result)
        )

    header = Window(
        FormattedTextControl(
            [
                ("class:report-label", "MEM FIND\n"),
                (
                    "class:report-neutral",
                    "READ-ONLY · PROVIDER-FREE · LITERAL OR EXPLICIT REGEX",
                ),
            ]
        ),
        height=2,
    )
    pattern_frame = build_focused_frame(
        pattern_area,
        title=" PATTERN · ENTER TO RUN ",
        is_focused=lambda: app.layout.has_focus(pattern_area),
        height=3,
    )
    target_frame = build_focused_frame(
        target_window,
        title=" CONTEXT · ALL READABLE CONTEXTS ",
        is_focused=lambda: app.layout.has_focus(target_control),
        height=Dimension(min=7, preferred=10, max=14),
    )
    scope_frame = build_focused_frame(
        Window(scope_control, height=5),
        title=" SCOPE ",
        is_focused=lambda: app.layout.has_focus(scope_control),
        height=7,
    )
    result_frame = build_focused_frame(
        results_window,
        title=" RESULTS ",
        is_focused=lambda: app.layout.has_focus(results_control),
    )
    status_window = Window(
        FormattedTextControl(lambda: [("class:memcommit.notification", status)]),
        height=1,
    )
    footer = Window(
        FormattedTextControl(
            "Tab/Shift-Tab move · Enter run/select · ←/→ change "
            "· y focused · Y all · Esc/Q close"
        ),
        height=1,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(pattern_frame, separator_before=True),
        TuiRegion(target_frame, separator_before=True),
        TuiRegion(scope_frame, separator_before=True),
        TuiRegion(result_frame, separator_before=True),
        TuiRegion(status_window),
        TuiRegion(footer),
    )
    app = Application(
        layout=Layout(root, focused_element=pattern_area),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=True,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        input=app_input,
        output=app_output,
    )
    return app.run()


__all__ = ["run_literal_find_tui"]
