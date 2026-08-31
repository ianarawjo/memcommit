"""Compact interactive provider-free Find setup and result Viewer."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down, scroll_page_up
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.adapters.console.clipboard import ClipboardError
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.readable_scope_editor import (
    CompactReadableScopeControl,
)
from memcommit.adapters.console.commands.find.presentation import (
    project_find_match,
    render_find_result,
)
from memcommit.adapters.console.terminal.components.retrieve_answer_save import (
    RetrieveAnswerSavePanel,
)
from memcommit.adapters.console.terminal.core.capabilities import require_interactive_terminal
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.commands.find.source_row import (
    render_find_reference_row,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import suggest_fresh_context_name
from memcommit.adapters.console.terminal.components.selection import (
    FlatMultiSelectionState,
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.selection.multiple import (
    render_vertical_multi_choice_rows,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.adapters.console.commands.find.workbench.model import (
    FindTuiOutcome,
    FindTuiSetup,
)
from memcommit.application.operations.find.application import (
    FindRequest,
    FindResult,
)
from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextMode,
)


FindRunner = Callable[[FindRequest], FindResult]


def _choice(*values: tuple[str, str], selected: str) -> HorizontalChoiceState:
    return HorizontalChoiceState(
        tuple(HorizontalChoiceOption(uid, label) for uid, label in values),
        selected_uid=selected,
    )


def _find_save_location_stem(context_name: str, pattern: str) -> str:
    words = "-".join(pattern.strip().split()) or "find"
    safe = "".join(
        "-" if character in "/\\:" or ord(character) < 32 else character
        for character in words
    ).strip("-.")
    if not safe:
        safe = "find"
    return f"{context_name}/results/{safe[:48].rstrip('-.') or 'find'}"


def _render_match_content(
    result: FindResult,
    selected_index: int,
    *,
    surface_focused: bool,
):
    if not result.matches:
        return [
            (
                "",
                (
                    "(scope contains no searchable Memories)"
                    if result.scanned_item_count == 0
                    else "(no matching Memories)"
                ),
            )
        ]
    fragments: list[tuple[str, str]] = []
    for index, match in enumerate(result.matches):
        active = index == selected_index
        if active and surface_focused:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                (
                    focused_control_style(
                        focused=surface_focused,
                        selected=True,
                    )
                    if active
                    else ""
                ),
                safe_terminal_text(
                    render_find_reference_row(
                        match,
                        number=index + 1,
                    )
                ),
            )
        )
        if index < len(result.matches) - 1:
            fragments.append(("", "\n"))
    return fragments


def run_find_workbench(
    request: FindRequest | None,
    *,
    setup: FindTuiSetup,
    execute: FindRunner,
    clipboard_writer: Callable[[str], None] | None = None,
    local_context_names: Sequence[str] | None = None,
    validate_save_location: Callable[[str], object] | None = None,
    initial_all_readable_contexts: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FindTuiOutcome | None:
    """Edit one exact request, run explicitly, and inspect complete matches."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Find",
            snapshot_hint='Pass a pattern, for example: mem find "parking".',
        )
    if not isinstance(setup, FindTuiSetup):
        raise TypeError("Find TUI requires a FindTuiSetup.")
    if request is not None and not isinstance(request, FindRequest):
        raise TypeError("Find TUI request must be a FindRequest or None.")
    if type(initial_all_readable_contexts) is not bool:
        raise TypeError("Find initial all-readable choice must be a boolean.")
    if not callable(execute):
        raise TypeError("Find TUI requires an execution callback.")
    local_catalog = tuple(
        dict.fromkeys(
            setup.names if local_context_names is None else local_context_names
        )
    )
    if any(not isinstance(name, str) or not name for name in local_catalog):
        raise ValueError("Find local Context names must be nonblank text.")

    initial_targets = setup.initial_targets if request is None else request.target_names
    if any(name not in setup.names for name in initial_targets):
        raise ValueError(
            "A selected Context is no longer available. "
            "Reopen Find and select it again."
        )

    mode_choice = _choice(
        ("LITERAL", "LITERAL"),
        ("REGEX", "REGEX"),
        selected="LITERAL" if request is None else request.mode,
    )
    case_choice = _choice(
        ("SENSITIVE", "SENSITIVE"),
        ("IGNORE", "IGNORE CASE"),
        selected="IGNORE"
        if request is not None and request.ignore_case
        else "SENSITIVE",
    )
    result: FindResult | None = None
    result_selection: FlatMultiSelectionState | None = None
    settings_row = 0
    status = "ENTER A PATTERN"
    bindings = KeyBindings()

    pattern_area = TextArea(
        text="" if request is None else request.pattern,
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        name="find-pattern",
    )

    def clear_result(message: str = "REQUEST CHANGED · PRESS ENTER TO RUN") -> None:
        nonlocal result, result_selection, status
        result = None
        result_selection = None
        status = message

    def set_status(message: str) -> None:
        nonlocal status
        status = safe_terminal_text(message).upper()

    scope = CompactReadableScopeControl(
        setup.names,
        current_name=setup.current_name,
        initial_targets=initial_targets,
        include_descendants=False if request is None else request.include_descendants,
        follow_embeds=request is not None and request.follow_embeds,
        annotations=dict(setup.annotations),
        input_name="find-context",
        on_change=clear_result,
        on_status=set_status,
    )
    pattern_area.buffer.on_text_changed += lambda _buffer: clear_result()

    initial_save_location = suggest_fresh_context_name(
        _find_save_location_stem(
            setup.initial_targets[0],
            "find" if request is None else request.pattern,
        ),
        local_catalog,
    )
    save_panel = RetrieveAnswerSavePanel(
        content_summary=lambda: (
            f"{len(result_selection.selected_uids)} CHECKED FIND MATCH(ES)"
            if result_selection is not None
            else "CHECK FIND MATCHES TO SAVE"
        ),
        action_label=lambda mode: (
            f"SAVE {len(result_selection.selected_uids)} CHECKED AS {mode}"
            if result_selection is not None
            else "SAVE CHECKED FIND MATCHES"
        ),
        initial_location=initial_save_location,
        context_names=local_catalog,
        current_context=(
            setup.current_name if setup.current_name in local_catalog else None
        ),
        validate_location=validate_save_location,
        input_name="find-save-location",
        on_status=set_status,
        mode_options=(
            HorizontalChoiceOption("COPY", "COPY"),
            HorizontalChoiceOption("REFERENCE", "REFERENCE"),
            HorizontalChoiceOption("EMBED", "EMBED"),
        ),
        initial_mode="COPY",
    )
    save_location_edit = {"edited": False, "programmatic": False}

    def save_location_changed(_buffer) -> None:
        if not save_location_edit["programmatic"]:
            save_location_edit["edited"] = True

    save_panel.name.input.buffer.on_text_changed += save_location_changed

    def render_settings():
        focused = app.layout.has_focus(settings_control)
        fragments = render_horizontal_choice(
            mode_choice,
            title="MATCH",
            focused=focused and settings_row == 0,
        )
        fragments.append(("", "\n"))
        fragments.extend(
            render_horizontal_choice(
                case_choice,
                title="CASE",
                focused=focused and settings_row == 1,
            )
        )
        return fragments

    settings_control = FormattedTextControl(
        render_settings,
        focusable=True,
        show_cursor=False,
    )

    def render_results():
        if result is None or result_selection is None:
            return [("", "Enter a pattern to search.")]
        if not result.matches:
            return [("", "(no matching Memories)")]
        return render_vertical_multi_choice_rows(
            result_selection,
            focused=app.layout.has_focus(results_control),
            content_width=max(24, app.output.get_size().columns - 6),
            numbered=False,
        )

    results_control = FormattedTextControl(render_results, focusable=True)
    results_window = Window(
        results_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
        always_hide_cursor=True,
    )

    def execute_request(_event=None):
        nonlocal result, result_selection, status
        pattern = pattern_area.text
        if not pattern:
            status = "PATTERN REQUIRED"
            app.layout.focus(pattern_area)
            return "HANDLED"
        try:
            targets, include_descendants = scope.request_scope()
            candidate = FindRequest(
                pattern=pattern,
                target_names=targets,
                include_descendants=include_descendants,
                follow_embeds=scope.follow_embeds,
                mode=mode_choice.selected_uid,
                ignore_case=case_choice.selected_uid == "IGNORE",
            )
            result = execute(candidate)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status = safe_terminal_text(str(error)).upper()
            if "CONTEXT" in status:
                app.layout.focus(scope.input)
            return "HANDLED"
        result_selection = (
            FlatMultiSelectionState(
                tuple(
                    SelectionOption(
                        str(index),
                        render_find_reference_row(match, number=index + 1),
                    )
                    for index, match in enumerate(result.matches)
                ),
                cursor_uid="0",
            )
            if result.matches
            else None
        )
        if result.matches and not save_location_edit["edited"]:
            save_location_edit["programmatic"] = True
            try:
                save_panel.set_location(
                    suggest_fresh_context_name(
                        _find_save_location_stem(
                            result.request.target_names[0],
                            result.request.pattern,
                        ),
                        local_catalog,
                    )
                )
            finally:
                save_location_edit["programmatic"] = False
        if result.matches:
            memory_label = "MEMORY" if len(result.matches) == 1 else "MEMORIES"
            occurrence_label = (
                "OCCURRENCE" if result.occurrence_count == 1 else "OCCURRENCES"
            )
            status = (
                f"{len(result.matches)} {memory_label}"
                f" · {result.occurrence_count} {occurrence_label}"
            )
            if result.identity_match_count:
                uid_label = (
                    "UID MATCH"
                    if result.identity_match_count == 1
                    else "UID MATCHES"
                )
                status += f" · {result.identity_match_count} {uid_label}"
        else:
            memory_label = "MEMORY" if result.scanned_item_count == 1 else "MEMORIES"
            status = f"NO MATCHES · {result.scanned_item_count} {memory_label} SCANNED"
        app.layout.focus(results_control)
        return "HANDLED"

    def move_settings(_event, delta: int):
        nonlocal settings_row
        candidate = settings_row + delta
        if not 0 <= candidate <= 1:
            return "BOUNDARY"
        settings_row = candidate
        return "MOVED"

    def enter_settings(delta: int) -> None:
        nonlocal settings_row
        settings_row = 0 if delta > 0 else 1

    def focus_pattern(event):
        event.app.layout.focus(pattern_area)
        pattern_area.buffer.cursor_position = len(pattern_area.text)
        return "HANDLED"

    def move_results(_event, delta: int):
        if result is None or result_selection is None or not result.matches:
            return "BOUNDARY"
        return "MOVED" if result_selection.move(delta) else "BOUNDARY"

    def toggle_result(event):
        if result_selection is None or result is None or not result.matches:
            return focus_pattern(event)
        checked = result_selection.toggle_cursor()
        set_status(
            f"{'CHECKED' if checked else 'UNCHECKED'} MATCH "
            f"{result_selection.cursor_index + 1} · "
            f"{len(result_selection.selected_uids)} TOTAL"
        )
        event.app.invalidate()
        return "HANDLED"

    @bindings.add(" ", filter=has_focus(results_control), eager=True)
    def _toggle_result_space(event) -> None:
        toggle_result(event)

    def apply_save(event):
        if result is None or result_selection is None:
            set_status("RUN FIND AND CHECK AT LEAST ONE MATCH")
            return "HANDLED"
        selected_indices = tuple(
            int(uid) for uid in result_selection.selected_uids
        )
        if not selected_indices:
            set_status("CHECK AT LEAST ONE FIND MATCH")
            return "HANDLED"
        try:
            destination = save_panel.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            set_status(str(error))
            event.app.layout.focus(save_panel.name.input)
            return "HANDLED"
        mode = save_panel.selected_mode
        assert mode is not None
        event.app.exit(
            result=FindTuiOutcome(
                result=result,
                status="SAVE",
                selected_match_indices=selected_indices,
                save_as=cast(SaveContextMode, mode),
                save_location=destination,
            )
        )
        return "HANDLED"

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        if scope.browser_open:
            return (scope.browser_surface(uid_prefix="find-scope"),)
        if save_panel.browser_open:
            return (save_panel.browser_surface(uid_prefix="find-save"),)
        surfaces = [
            *scope.normal_surfaces(uid_prefix="find-scope"),
            FocusSurface(
                "settings",
                settings_control,
                move_vertical=move_settings,
                activate=focus_pattern,
                on_vertical_enter=enter_settings,
            ),
            FocusSurface("pattern", pattern_area, activate=execute_request),
            FocusSurface(
                "results",
                results_control,
                move_vertical=move_results,
                activate=toggle_result,
            ),
        ]
        if result is not None and result.matches:
            surfaces.extend(
                save_panel.normal_surfaces(
                    activate_action=apply_save,
                    uid_prefix="find-save",
                )
            )
        return tuple(surfaces)

    surfaces = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surfaces)
    scope.bind_keybindings(bindings)
    save_panel.bind_keybindings(bindings)

    @bindings.add("left", filter=has_focus(settings_control), eager=True)
    def _settings_left(event) -> None:
        _move_setting_choice(-1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(settings_control), eager=True)
    def _settings_right(event) -> None:
        _move_setting_choice(1)
        event.app.invalidate()

    def _move_setting_choice(delta: int) -> None:
        changed = (mode_choice if settings_row == 0 else case_choice).move(delta)
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
            render_find_result(
                result,
                all_readable_contexts=(
                    scope.profile_selected
                    or (
                        initial_all_readable_contexts
                        and result.request.target_names == setup.names
                    )
                ),
            )
            if whole or not result.matches
            else project_find_match(
                result.matches[
                    0
                    if result_selection is None
                    else result_selection.cursor_index
                ],
                number=(
                    1
                    if result_selection is None
                    else result_selection.cursor_index + 1
                ),
            )
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

    @bindings.add("tab", filter=has_focus(scope.tree_control), eager=True)
    @bindings.add("s-tab", filter=has_focus(scope.tree_control), eager=True)
    @bindings.add("backspace", filter=has_focus(scope.tree_control), eager=True)
    def _leave_browser(event) -> None:
        scope.close_browser(event)
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        if not scope.close_browser(event) and not save_panel.close_browser(event):
            event.app.exit(result=None if result is None else FindTuiOutcome(result))
        event.app.invalidate()

    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(result=None if result is None else FindTuiOutcome(result))

    writable_focus = (
        has_focus(pattern_area)
        | has_focus(scope.input)
        | has_focus(save_panel.name.input)
    )

    @bindings.add("q", filter=~writable_focus, eager=True)
    def _close_q(event) -> None:
        event.app.exit(result=None if result is None else FindTuiOutcome(result))

    header = Window(
        FormattedTextControl([("class:report-label", "MEM FIND")]),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    scope_frame = build_focused_frame(
        scope.container,
        title=" SCOPE ",
        is_focused=lambda: any(
            app.layout.has_focus(control)
            for control in (
                scope.input,
                scope.browse_control,
                scope.range_control,
                scope.embed_control,
                scope.tree_control,
            )
        ),
    )
    find_frame = build_focused_frame(
        HSplit(
            [
                Window(settings_control, height=Dimension.exact(2), wrap_lines=False),
                Window(FormattedTextControl(""), height=Dimension.exact(1)),
                pattern_area,
            ]
        ),
        title=" FIND · ENTER PATTERN TO RUN ",
        is_focused=lambda: app.layout.has_focus(settings_control)
        or app.layout.has_focus(pattern_area),
        height=Dimension.exact(6),
    )
    result_frame = build_focused_frame(
        results_window,
        title=" RESULTS ",
        is_focused=lambda: app.layout.has_focus(results_control),
        height=Dimension(min=4, preferred=10, max=16),
    )
    status_window = Window(
        FormattedTextControl(lambda: [("class:memcommit.notification", status)]),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    footer = Window(
        FormattedTextControl(
            "Tab/Shift-Tab move · Enter run/check · ←/→ change · "
            "y focused · Y all · Esc close"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    save_container = ConditionalContainer(
        save_panel.container,
        filter=Condition(lambda: result is not None and bool(result.matches)),
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(scope_frame, separator_before=True),
        TuiRegion(find_frame, separator_before=True),
        TuiRegion(result_frame, separator_before=True),
        TuiRegion(save_container, separator_before=True),
        TuiRegion(status_window),
        TuiRegion(footer),
    )
    app: Application[FindTuiOutcome | None] = Application(
        layout=Layout(root, focused_element=pattern_area),
        key_bindings=bindings,
        full_screen=False,
        erase_when_done=True,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        input=app_input,
        output=app_output,
    )
    return app.run()


__all__ = ["run_find_workbench"]
