"""Shared terminal picker for inspecting or selecting temporal history items.

The picker deliberately receives presentation summaries rather than store
objects.  History reconstruction, semantic search, freshness validation, and
the eventual revert remain responsibilities of their command adapters.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable, Literal, Protocol, runtime_checkable

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.widgets import Frame

from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.history_display import history_action_style
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.interfaces.tui.components.frame import (
    bind_focused_frame_style,
)
from memcommit.interfaces.tui.components.scrollable_pane import (
    build_scrollable_formatted_text_pane,
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.core.text_layout import (
    AdaptiveColumn,
    allocate_adaptive_columns,
    elide_terminal_text,
    live_window_content_width,
    pad_terminal_text,
    terminal_cell_width,
)
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation


HistoryPickerMode = Literal["log", "revert"]
_VISIBLE_ROWS = 12


@runtime_checkable
class HistoryPickerItem(Protocol):
    """Minimal projection a checkpoint or temporal Find adapter must provide."""

    uid: str
    timestamp: str
    command: str
    description: str
    detail: str


@dataclass(frozen=True)
class HistoryPickerEntry:
    """Validated built-in implementation of :class:`HistoryPickerItem`."""

    uid: str
    timestamp: str
    command: str
    description: str
    detail: str

    def __post_init__(self) -> None:
        for label, value in (
            ("history UID", self.uid),
            ("history timestamp", self.timestamp),
            ("history command", self.command),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{label} must be non-empty text.")
        if not isinstance(self.description, str):
            raise ValueError("history description must be text.")
        if not isinstance(self.detail, str):
            raise ValueError("history detail must be text.")


@dataclass(frozen=True)
class HistorySelectionReceipt:
    """Exact local selection returned by the mutation-oriented picker mode."""

    context_name: str
    checkpoint_uid: str
    keep_history: bool = False


@dataclass(frozen=True)
class HistoryBackNavigation:
    """Read-only receipt requesting return to the owning previous screen."""


HISTORY_BACK = HistoryBackNavigation()


def _visible_bounds(selected: int, count: int) -> tuple[int, int]:
    visible = min(count, _VISIBLE_ROWS)
    start = max(0, selected - visible // 2)
    start = min(start, count - visible)
    return start, start + visible


def _compact_timestamp(value: str) -> str:
    return display_escape_text(value[:16].replace("T", " "))


def _compact(value: str, width: int) -> str:
    return elide_terminal_text(display_escape_text(value), width)


def _entry_line_parts(
    entry: HistoryPickerItem,
    *,
    entries: Sequence[HistoryPickerItem],
    selected: bool,
    checked: bool = False,
    available_width: int,
) -> tuple[str, str, str, str]:
    """Lay out one History row before presentation styles are applied."""

    pointer = "›" if selected else " "
    marker = "✓" if checked else " "
    timestamp = (
        f"{_compact_timestamp(entry.timestamp):<16}  " if available_width >= 58 else ""
    )
    uid = display_escape_text(entry.uid)[:8]
    prefix = f"{pointer}{marker} {timestamp}"
    suffix = f"  {uid}  "
    field_budget = max(
        0,
        available_width - terminal_cell_width(prefix + suffix),
    )
    commands = tuple(display_escape_text(item.command) for item in entries)
    descriptions = tuple(
        display_escape_text(item.description or "(no description)") for item in entries
    )
    command_natural = max(
        (terminal_cell_width(value) for value in commands),
        default=0,
    )
    description_natural = max(
        (terminal_cell_width(value) for value in descriptions),
        default=0,
    )
    widths = allocate_adaptive_columns(
        field_budget,
        (
            AdaptiveColumn(
                "command",
                minimum=min(6, command_natural),
                preferred=command_natural,
                maximum=command_natural,
                shrink_order=1,
                grow_order=0,
            ),
            AdaptiveColumn(
                "description",
                minimum=min(10, description_natural),
                preferred=description_natural,
                shrink_order=0,
                grow_order=1,
                expand=True,
            ),
        ),
    )
    command = pad_terminal_text(
        elide_terminal_text(display_escape_text(entry.command), widths["command"]),
        widths["command"],
    )
    description = elide_terminal_text(
        display_escape_text(entry.description or "(no description)"),
        widths["description"],
    )
    return prefix, command, suffix, description


def _render_entry_line(
    entry: HistoryPickerItem,
    *,
    entries: Sequence[HistoryPickerItem],
    selected: bool,
    checked: bool = False,
    available_width: int,
) -> str:
    """Render the stable plain projection of one History Items row."""

    return elide_terminal_text(
        "".join(
            _entry_line_parts(
                entry,
                entries=entries,
                selected=selected,
                checked=checked,
                available_width=available_width,
            )
        ),
        available_width,
    )


def _render_entry_fragments(
    entry: HistoryPickerItem,
    *,
    entries: Sequence[HistoryPickerItem],
    selected: bool,
    checked: bool = False,
    available_width: int,
) -> StyleAndTextTuples:
    """Color only the action token; keyboard focus still owns the whole row."""

    parts = _entry_line_parts(
        entry,
        entries=entries,
        selected=selected,
        checked=checked,
        available_width=available_width,
    )
    rendered = "".join(parts)
    focused_style = "class:memcommit.table.selected" if selected else ""
    if terminal_cell_width(rendered) > available_width:
        return [(focused_style, elide_terminal_text(rendered, available_width))]
    prefix, command, suffix, description = parts
    return [
        (focused_style, prefix),
        (
            focused_style or f"class:{history_action_style(entry.command)}",
            command,
        ),
        (focused_style, suffix + description),
    ]


def _indented_detail(value: str) -> tuple[str, ...]:
    """Keep item content visibly subordinate to the trusted metadata labels."""
    # Only explicit LF characters retain layout meaning. Tabs, carriage
    # returns, bidi controls, Unicode separators, and backslashes remain
    # visible escapes so item content cannot imitate the trusted frame.
    lines = tuple(
        display_escape_text(line) for line in (value or "(no detail)").split("\n")
    )
    return (
        f" Detail       {lines[0]}",
        *(f"              {line}" for line in lines[1:]),
    )


def _render_detail(entry: HistoryPickerItem) -> str:
    """Render the complete selected record through a single-line trust boundary."""
    description = entry.description or "(no description)"
    return "\n".join(
        (
            f" UID          {display_escape_text(entry.uid)}",
            f" Time         {display_escape_text(entry.timestamp)}",
            f" Command      {display_escape_text(entry.command)}",
            f" Description  {display_escape_text(description)}",
            *_indented_detail(entry.detail),
        )
    )


def choose_history(
    entries: Sequence[HistoryPickerItem],
    *,
    context_name: str,
    mode: HistoryPickerMode,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    initial_details_open: bool | None = None,
    detail_renderer: (
        Callable[[HistoryPickerItem], str | StyleAndTextTuples] | None
    ) = None,
    empty_message: str | None = None,
    empty_detail: str | None = None,
    back_navigation: bool = False,
    title: str | None = None,
    workbench_navigation: SessionWorkbenchNavigation | None = None,
    keep_history: bool = False,
    staged_checkpoint_uid: str | None = None,
) -> HistorySelectionReceipt | HistoryBackNavigation | None:
    """Inspect history or return one exact checkpoint selection.

    In ``log`` mode Enter opens the selected checkpoint in Viewer and only a
    close/cancel key exits. In ``revert`` mode Enter stages an exact checkpoint,
    then the History and Apply frames review its retention policy before this
    function returns a receipt. This function never performs a revert. Arrow
    keys traverse Viewer and Items at their real content boundaries.
    """
    options = tuple(entries)
    if not isinstance(context_name, str) or not context_name:
        raise ValueError("History selection requires a Context name.")
    if mode not in {"log", "revert"}:
        raise ValueError("History picker mode must be 'log' or 'revert'.")
    if not options and not empty_message:
        raise ValueError("No history entries are available to select.")
    if any(not isinstance(entry, HistoryPickerItem) for entry in options):
        raise ValueError("History selection received an invalid entry.")
    for entry in options:
        for value in (
            entry.uid,
            entry.timestamp,
            entry.command,
            entry.description,
            entry.detail,
        ):
            if not isinstance(value, str):
                raise ValueError("History selection received an invalid entry.")
    if len({entry.uid for entry in options}) != len(options):
        raise ValueError("History selection received duplicate entry UIDs.")
    if detail_renderer is not None and not callable(detail_renderer):
        raise ValueError("History detail renderer must be callable.")
    if initial_details_open is not None and not isinstance(initial_details_open, bool):
        raise ValueError("History initial detail state must be boolean.")
    if not isinstance(keep_history, bool):
        raise ValueError("History preservation state must be boolean.")
    if staged_checkpoint_uid is not None and (
        mode != "revert"
        or staged_checkpoint_uid not in {entry.uid for entry in options}
    ):
        raise ValueError(
            "A staged Revert checkpoint must belong to the visible history."
        )
    for value, label in (
        (empty_detail, "History empty detail"),
        (title, "History picker title"),
    ):
        if value is not None and (
            not isinstance(value, str)
            or not value
            or (label == "History picker title" and "\n" in value)
        ):
            raise ValueError(f"{label} must be non-empty text.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive history selection requires a terminal. "
            "Pass a checkpoint UID explicitly or use plain log output."
        )

    navigation = workbench_navigation or SessionWorkbenchNavigation(pane="items")
    navigation.focus("items")
    staged_row = next(
        (
            index
            for index, entry in enumerate(options)
            if entry.uid == staged_checkpoint_uid
        ),
        0,
    )
    navigation.move_row(len(options), staged_row)
    navigation.preview_selected_row()
    # History now follows the shared Items/Viewer contract by default.  The
    # explicit override remains for compatibility with callers that want an
    # initial closed placeholder before the first Enter.
    details_open = {
        "value": True if initial_details_open is None else initial_details_open
    }
    selected_checkpoint = {"uid": staged_checkpoint_uid}
    history_policy = (
        HorizontalChoiceState(
            (
                HorizontalChoiceOption(
                    "DISCARD_NEWER",
                    "DISCARD NEWER",
                    (
                        "Remove newer visible checkpoints after restoration; "
                        "the recovery checkpoint retains undo metadata."
                    ),
                ),
                HorizontalChoiceOption(
                    "KEEP_ALL",
                    "KEEP ALL",
                    "Preserve every currently visible checkpoint after restoration.",
                ),
            ),
            selected_uid="KEEP_ALL" if keep_history else "DISCARD_NEWER",
        )
        if mode == "revert" and options
        else None
    )
    bindings = KeyBindings()
    app_ref: dict[
        str, Application[HistorySelectionReceipt | HistoryBackNavigation | None]
    ] = {}

    def render_entries() -> list[tuple[str, str]]:
        if not options:
            return [
                (
                    "class:report-neutral",
                    f"  {display_escape_text(empty_message or '')}",
                )
            ]
        start, end = _visible_bounds(navigation.row_index, len(options))
        visible = options[start:end]
        available_width = live_window_content_width(
            options_window,
            fallback_reserved=3,
        )
        fragments: list[tuple[str, str]] = []
        for index in range(start, end):
            entry = options[index]
            selected = index == navigation.row_index
            if selected:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.extend(
                _render_entry_fragments(
                    entry,
                    entries=visible,
                    selected=selected,
                    checked=(
                        mode == "revert" and entry.uid == selected_checkpoint["uid"]
                    ),
                    available_width=available_width,
                )
            )
            if index < end - 1:
                fragments.append(("", "\n"))
        return fragments

    def render_detail() -> str | StyleAndTextTuples:
        if not options:
            return empty_detail or " No history item is available."
        if not details_open["value"]:
            return " Select an item and press Enter to open its detail."
        entry = options[navigation.viewer_row_index]
        return (
            detail_renderer(entry)
            if detail_renderer is not None
            else _render_detail(entry)
        )

    def render_footer() -> str:
        close = (
            "Esc/Backspace back  q close"
            if back_navigation
            else "Esc/Backspace/q close"
        )
        if not options:
            return f" {close}  ·  0/0"
        position = f"{navigation.row_index + 1}/{len(options)}"
        app = app_ref.get("app")
        if app is not None and app.layout.has_focus(detail_pane.text_area):
            return (
                " FOCUS VIEWER · ↑/↓ scroll  Enter/Esc/Backspace items  "
                f"Tab switch  q close  ·  {position}"
            )
        if (
            history_policy is not None
            and app is not None
            and app.layout.has_focus(policy_control)
        ):
            return (
                " FOCUS HISTORY · ←/→ select  Enter apply  "
                f"Esc/Backspace items  Tab switch  q cancel  ·  {position}"
            )
        if (
            history_policy is not None
            and app is not None
            and app.layout.has_focus(apply_control)
        ):
            return (
                " FOCUS APPLY · Enter revert exact checkpoint  "
                f"Esc/Backspace history  Tab switch  q cancel  ·  {position}"
            )
        if mode == "revert":
            action = "Enter select exact UID"
            close = (
                "Esc/Backspace back  q cancel"
                if back_navigation
                else "Esc/Backspace/q cancel"
            )
        else:
            action = "Enter viewer"
        return f" FOCUS ITEMS · ↑/↓ move  {action}  Tab switch  {close}  ·  {position}"

    list_control = FormattedTextControl(
        text=render_entries,
        focusable=True,
        show_cursor=False,
    )
    options_window = Window(
        list_control,
        height=Dimension(
            min=1,
            preferred=min(len(options), _VISIBLE_ROWS),
            max=_VISIBLE_ROWS,
            weight=3,
        ),
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    detail_pane = build_scrollable_formatted_text_pane(
        "VIEWER",
        render_detail(),
        height=Dimension(min=6, preferred=14, weight=7),
    )
    detail_window = detail_pane.text_area.window

    def sync_detail(*, anchor: Literal["preserve", "start", "end"]) -> None:
        detail_pane.set_formatted_text(render_detail(), anchor=anchor)

    def move_items(_event, delta: int) -> SurfaceMoveResult:
        if not options:
            return "BOUNDARY"
        before = navigation.row_index
        navigation.move_and_preview_row(len(options), delta)
        if navigation.row_index == before:
            return "BOUNDARY"
        sync_detail(anchor="start")
        return "MOVED"

    def move_viewer(event, delta: int) -> SurfaceMoveResult:
        return (
            "MOVED" if move_wrapped_read_cursor(event, direction=delta) else "BOUNDARY"
        )

    def enter_viewer(delta: int) -> None:
        detail_pane.text_area.buffer.cursor_position = (
            0 if delta > 0 else len(detail_pane.text_area.text)
        )

    def focus_viewer() -> None:
        navigation.focus("viewer")

    def focus_items() -> None:
        navigation.focus("items")

    def activate_items(event) -> SurfaceActionResult:
        if not options:
            return "HANDLED"
        if mode == "revert":
            selected_checkpoint["uid"] = options[navigation.row_index].uid
            surface_focus.focus_relative(event.app, 1, wrap=False)
            return "HANDLED"
        details_open["value"] = True
        sync_detail(anchor="start")
        navigation.open_selected()
        surface_focus.focus_relative(event.app, -1, wrap=False)
        return "ENTER_CHILD"

    def activate_viewer(event) -> SurfaceActionResult:
        surface_focus.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def back_viewer(event) -> SurfaceActionResult:
        surface_focus.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def back_items(event) -> SurfaceActionResult:
        event.app.exit(result=HISTORY_BACK if back_navigation else None)
        return "HANDLED"

    def move_policy(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def activate_policy(event) -> SurfaceActionResult:
        surface_focus.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def back_policy(event) -> SurfaceActionResult:
        surface_focus.focus_relative(event.app, -1, wrap=False)
        return "HANDLED"

    def move_apply(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def activate_apply(event) -> SurfaceActionResult:
        uid = selected_checkpoint["uid"]
        if uid is None or history_policy is None:
            return "HANDLED"
        event.app.exit(
            result=HistorySelectionReceipt(
                context_name=context_name,
                checkpoint_uid=uid,
                keep_history=history_policy.selected_uid == "KEEP_ALL",
            )
        )
        return "HANDLED"

    def back_apply(event) -> SurfaceActionResult:
        surface_focus.focus_relative(event.app, -1, wrap=False)
        return "HANDLED"

    policy_control = FormattedTextControl(
        lambda: (
            render_horizontal_choice(
                history_policy,
                title="NEWER CHECKPOINTS",
                focused=(
                    app_ref.get("app") is not None
                    and app_ref["app"].layout.has_focus(policy_control)
                ),
                show_description=True,
                inline_boxed=True,
            )
            if history_policy is not None
            else []
        ),
        focusable=history_policy is not None,
        show_cursor=False,
    )
    policy_frame = Frame(
        Window(policy_control, height=2, dont_extend_height=True),
        title="HISTORY",
    )

    def render_apply() -> StyleAndTextTuples:
        focused = app_ref.get("app") is not None and app_ref["app"].layout.has_focus(
            apply_control
        )
        uid = selected_checkpoint["uid"]
        if uid is None or history_policy is None:
            label = "SELECT A CHECKPOINT FIRST"
        else:
            policy = (
                "KEEP ALL CHECKPOINTS"
                if history_policy.selected_uid == "KEEP_ALL"
                else "DISCARD NEWER CHECKPOINTS"
            )
            label = f"REVERT TO {uid[:8]} · {policy}"
        return [
            ("[SetCursorPosition]", ""),
            (focused_control_style(focused=focused), f"[ {label} ]"),
        ]

    apply_control = FormattedTextControl(
        render_apply,
        focusable=history_policy is not None,
        show_cursor=False,
    )
    apply_frame = Frame(
        Window(apply_control, height=1, dont_extend_height=True),
        title="APPLY",
    )

    surfaces = [
        FocusSurface(
            "viewer",
            detail_pane.text_area,
            move_vertical=move_viewer,
            activate=activate_viewer,
            back=back_viewer,
            on_focus=focus_viewer,
            on_vertical_enter=enter_viewer,
        ),
        FocusSurface(
            "items",
            list_control,
            move_vertical=move_items,
            activate=activate_items,
            back=back_items,
            on_focus=focus_items,
        ),
    ]
    if history_policy is not None:
        surfaces.extend(
            (
                FocusSurface(
                    "history-policy",
                    policy_control,
                    move_vertical=move_policy,
                    activate=activate_policy,
                    back=back_policy,
                ),
                FocusSurface(
                    "apply",
                    apply_control,
                    move_vertical=move_apply,
                    activate=activate_apply,
                    back=back_apply,
                ),
            )
        )
    surface_focus = SurfaceFocusController(tuple(surfaces))
    bind_surface_navigation(bindings, surface_focus, back=True)

    if history_policy is not None:
        policy_focused = has_focus(policy_control)

        @bindings.add("left", filter=policy_focused, eager=True)
        def _policy_left(event) -> None:
            history_policy.move(-1)
            event.app.invalidate()

        @bindings.add("right", filter=policy_focused, eager=True)
        def _policy_right(event) -> None:
            history_policy.move(1)
            event.app.invalidate()

    viewer_focused = has_focus(detail_pane.text_area)

    @bindings.add("pageup", filter=viewer_focused, eager=True)
    def _page_up(event) -> None:
        scroll_wrapped_page(event, direction=-1)

    @bindings.add("pagedown", filter=viewer_focused, eager=True)
    def _page_down(event) -> None:
        scroll_wrapped_page(event, direction=1)

    @bindings.add("home", filter=viewer_focused, eager=True)
    def _home(event) -> None:
        detail_pane.text_area.buffer.cursor_position = 0
        detail_window.vertical_scroll = 0
        detail_window.vertical_scroll_2 = 0
        event.app.invalidate()

    @bindings.add("end", filter=viewer_focused, eager=True)
    def _end(event) -> None:
        detail_pane.text_area.buffer.cursor_position = len(detail_pane.text_area.text)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(
            " "
            + (
                display_escape_text(title)
                if title is not None
                else ("HISTORY" if mode == "log" else "REVERT")
            )
            + " · "
            + display_escape_text(context_name)
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    viewer_frame = detail_pane.frame
    items_frame = Frame(options_window, title="ITEMS")
    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    body: list[object] = [
        header,
        viewer_frame,
        items_frame,
    ]
    if history_policy is not None:
        body.extend((policy_frame, apply_frame))
    body.append(footer)
    app: Application[HistorySelectionReceipt | HistoryBackNavigation | None] = (
        Application(
            layout=Layout(
                HSplit(body),
                focused_element=(
                    policy_control
                    if staged_checkpoint_uid is not None
                    else list_control
                ),
            ),
            key_bindings=bindings,
            full_screen=True,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        )
    )
    app_ref["app"] = app
    for control, frame in (
        (detail_pane.text_area, viewer_frame),
        (list_control, items_frame),
        *(
            (
                (policy_control, policy_frame),
                (apply_control, apply_frame),
            )
            if history_policy is not None
            else ()
        ),
    ):
        bind_focused_frame_style(
            frame,
            is_focused=lambda control=control: app.layout.has_focus(control),
        )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
