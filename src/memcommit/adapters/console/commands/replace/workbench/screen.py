"""Compact direct-execution workbench for deterministic Replace."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.readable_scope_editor import (
    CompactReadableScopeControl,
)
from memcommit.adapters.console.terminal.core.capabilities import require_interactive_terminal
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
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
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.commands.replace.workbench.model import ReplaceTuiSetup
from memcommit.application.operations.replace.application import (
    ReplaceApplyResult,
    ReplaceRequest,
)


ReplaceRunner = Callable[[ReplaceRequest], ReplaceApplyResult]


def _choice(*values: tuple[str, str], selected: str) -> HorizontalChoiceState:
    return HorizontalChoiceState(
        tuple(HorizontalChoiceOption(uid, label) for uid, label in values),
        selected_uid=selected,
    )


def run_replace_tui(
    request: ReplaceRequest | None,
    *,
    setup: ReplaceTuiSetup,
    execute: ReplaceRunner,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ReplaceApplyResult | None:
    """Edit one exact request and execute it without a review session."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Replace",
            snapshot_hint='Execute directly with mem replace "old" "new".',
        )
    if not isinstance(setup, ReplaceTuiSetup):
        raise TypeError("Replace TUI requires a ReplaceTuiSetup.")
    if request is not None and not isinstance(request, ReplaceRequest):
        raise TypeError("Replace TUI request must be a ReplaceRequest or None.")
    if not callable(execute):
        raise TypeError("Replace TUI requires an execution callback.")

    initial_targets = setup.initial_targets if request is None else request.target_names
    if any(name not in setup.names for name in initial_targets):
        raise ValueError(
            "A selected Context is no longer available. "
            "Reopen Replace and select it again."
        )

    mode_choice = _choice(
        ("LITERAL", "LITERAL"),
        ("REGEX", "REGEX"),
        selected="LITERAL" if request is None else request.mode,
    )
    case_choice = _choice(
        ("SENSITIVE", "SENSITIVE"),
        ("IGNORE", "IGNORE CASE"),
        selected=(
            "IGNORE" if request is not None and request.ignore_case else "SENSITIVE"
        ),
    )
    settings_row = 0
    status = (
        "ENTER FIND AND REPLACEMENT TEXT"
        if request is None
        else "PRESS ENTER ON REPLACE WITH TO RUN"
    )
    bindings = KeyBindings()

    pattern_area = TextArea(
        text="" if request is None else request.pattern,
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        name="replace-pattern",
    )
    replacement_area = TextArea(
        text="" if request is None else request.replacement,
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        name="replace-value",
    )

    def set_status(message: str) -> None:
        nonlocal status
        status = safe_terminal_text(message).upper()

    def request_changed(_message: str = "") -> None:
        set_status("REQUEST CHANGED · ENTER REPLACE WITH TO RUN")

    scope = CompactReadableScopeControl(
        setup.names,
        current_name=setup.current_name,
        initial_targets=initial_targets,
        include_descendants=False if request is None else request.include_descendants,
        follow_embeds=request is not None and request.follow_embeds,
        input_name="replace-context",
        on_change=request_changed,
        on_status=set_status,
    )
    pattern_area.buffer.on_text_changed += lambda _buffer: request_changed()
    replacement_area.buffer.on_text_changed += lambda _buffer: request_changed()

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

    def focus_pattern(event):
        event.app.layout.focus(pattern_area)
        pattern_area.buffer.cursor_position = len(pattern_area.text)
        return "HANDLED"

    def focus_replacement(event):
        if not pattern_area.text:
            set_status("FIND TEXT REQUIRED")
            event.app.layout.focus(pattern_area)
            return "HANDLED"
        event.app.layout.focus(replacement_area)
        replacement_area.buffer.cursor_position = len(replacement_area.text)
        set_status("ENTER REPLACE WITH TO RUN · EMPTY REMOVES MATCHED TEXT")
        return "HANDLED"

    def execute_request(event):
        if not pattern_area.text:
            set_status("FIND TEXT REQUIRED")
            event.app.layout.focus(pattern_area)
            return "HANDLED"
        try:
            targets, include_descendants = scope.request_scope()
            candidate = ReplaceRequest(
                pattern=pattern_area.text,
                replacement=replacement_area.text,
                target_names=targets,
                # The compact scope already projects every visible descendant
                # into the exact checked execution set.
                include_descendants=include_descendants,
                follow_embeds=scope.follow_embeds,
                mode=mode_choice.selected_uid,
                ignore_case=case_choice.selected_uid == "IGNORE",
            )
            completed = execute(candidate)
            if not isinstance(completed, ReplaceApplyResult):
                raise TypeError("Replace application returned an invalid result.")
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            set_status(f"REPLACE STOPPED · {error}")
            return "HANDLED"
        event.app.exit(result=completed)
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

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        if scope.browser_open:
            return (scope.browser_surface(uid_prefix="replace-scope"),)
        return (
            *scope.normal_surfaces(uid_prefix="replace-scope"),
            FocusSurface(
                "settings",
                settings_control,
                move_vertical=move_settings,
                activate=focus_pattern,
                on_vertical_enter=enter_settings,
            ),
            FocusSurface("pattern", pattern_area, activate=focus_replacement),
            FocusSurface("replacement", replacement_area, activate=execute_request),
        )

    surfaces = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surfaces)
    scope.bind_keybindings(bindings)

    def move_setting_choice(delta: int) -> None:
        changed = (mode_choice if settings_row == 0 else case_choice).move(delta)
        if changed:
            request_changed()

    @bindings.add("left", filter=has_focus(settings_control), eager=True)
    def _settings_left(event) -> None:
        move_setting_choice(-1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(settings_control), eager=True)
    def _settings_right(event) -> None:
        move_setting_choice(1)
        event.app.invalidate()

    @bindings.add("tab", filter=has_focus(scope.tree_control), eager=True)
    @bindings.add("s-tab", filter=has_focus(scope.tree_control), eager=True)
    @bindings.add("backspace", filter=has_focus(scope.tree_control), eager=True)
    def _leave_browser(event) -> None:
        scope.close_browser(event)
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        if not scope.close_browser(event):
            event.app.exit(result=None)
        event.app.invalidate()

    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(result=None)

    writable_focus = (
        has_focus(pattern_area) | has_focus(replacement_area) | has_focus(scope.input)
    )

    @bindings.add("q", filter=~writable_focus, eager=True)
    def _close_q(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl([("class:report-label", "MEM REPLACE")]),
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
        title=" FIND ",
        is_focused=lambda: app.layout.has_focus(settings_control)
        or app.layout.has_focus(pattern_area),
        height=Dimension.exact(6),
    )
    replacement_frame = build_focused_frame(
        replacement_area,
        title=" REPLACE WITH · EMPTY REMOVES MATCHED TEXT ",
        is_focused=lambda: app.layout.has_focus(replacement_area),
        height=Dimension.exact(3),
    )
    status_window = Window(
        FormattedTextControl(lambda: [("class:memcommit.notification", status)]),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    footer = Window(
        FormattedTextControl(
            "Tab/Shift-Tab move · Enter stage/run · ←/→ change · Esc close"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(scope_frame, separator_before=True),
        TuiRegion(find_frame, separator_before=True),
        TuiRegion(replacement_frame),
        TuiRegion(status_window),
        TuiRegion(footer),
    )
    app: Application[ReplaceApplyResult | None] = Application(
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


__all__ = ["run_replace_tui"]
