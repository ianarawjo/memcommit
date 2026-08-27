"""Operation-neutral launcher for frozen operation entries and actions.

The picker receives a frozen presentation catalog and returns a local
selection receipt.  Catalog discovery, freshness validation, persistence, provider
calls, and command execution deliberately remain responsibilities of the
operation adapter.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea

from memcommit.adapters.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.adapters.console.text import (
    display_escape_text,
)
from memcommit.adapters.interfaces.tui.components.frame import (
    horizontal_rule,
)
from memcommit.adapters.interfaces.tui.components.operation_launcher.model import (
    LauncherAction,
    LauncherActionSelection,
    LauncherEntry,
    LauncherEntrySelection,
    LauncherGroupMode,
    LauncherOrientation,
    LauncherSelection,
    LauncherSortMode,
    OperationLauncherSpec,
)
from memcommit.adapters.interfaces.tui.core.text_layout import (
    AdaptiveColumn,
    allocate_adaptive_columns,
    elide_terminal_text,
    live_window_content_width,
    pad_terminal_text,
    terminal_cell_width,
)


_VISIBLE_ROWS = 12


@dataclass
class _PickerState:
    selected_index: int = 0
    new_selected: bool = False
    sort_mode: LauncherSortMode = "recent"
    group_mode: LauncherGroupMode = "all"
    search_active: bool = False
    search_before_edit: str = ""


def _entry_identity(entry: LauncherEntry) -> tuple[str, str]:
    return entry.kind, entry.key


def _matches_filter(entry: LauncherEntry, query: str) -> bool:
    needle = query.casefold().strip()
    if not needle:
        return True
    return any(
        needle in value.casefold()
        for value in (
            entry.kind,
            entry.key,
            entry.title,
            entry.status,
            entry.subtitle,
            entry.group,
            entry.detail,
        )
    )


def _ordered_entries(
    entries: Sequence[LauncherEntry],
    *,
    sort_mode: LauncherSortMode,
    group_mode: LauncherGroupMode,
    query: str = "",
) -> tuple[LauncherEntry, ...]:
    """Return one deterministic projection without changing the catalog."""
    filtered = [entry for entry in entries if _matches_filter(entry, query)]

    def recent_key(entry: LauncherEntry) -> tuple[object, ...]:
        return (
            -float(entry.sort_timestamp),
            entry.title.casefold(),
            entry.kind.casefold(),
            entry.key,
        )

    def name_key(entry: LauncherEntry) -> tuple[object, ...]:
        return (
            entry.title.casefold(),
            entry.kind.casefold(),
            entry.key,
        )

    item_key = recent_key if sort_mode == "recent" else name_key
    if group_mode == "context":
        return tuple(
            sorted(
                filtered,
                key=lambda entry: (
                    entry.group.casefold(),
                    entry.group,
                    *item_key(entry),
                ),
            )
        )
    return tuple(sorted(filtered, key=item_key))


def _visible_bounds(
    selected: int,
    count: int,
    *,
    line_budget: int = _VISIBLE_ROWS,
) -> tuple[int, int]:
    if count == 0:
        return 0, 0
    visible = min(count, line_budget)
    start = max(0, selected - visible // 2)
    start = min(start, count - visible)
    return start, start + visible


def _visible_grouped_bounds(
    entries: Sequence[LauncherEntry],
    selected: int,
    *,
    line_budget: int = _VISIBLE_ROWS,
) -> tuple[int, int]:
    """Keep a grouped slice within the list's display-line budget.

    Context headings and separators consume lines that the flat entry window
    does not. Bounding by entries alone can make the selected row disappear
    inside prompt_toolkit's second scrolling layer when many Contexts are
    adjacent.
    """
    start, end = _visible_bounds(
        selected,
        len(entries),
        line_budget=line_budget,
    )

    while (
        start < end
        and _grouped_line_count(entries, start=start, end=end) > line_budget
    ):
        left_distance = selected - start
        right_distance = (end - 1) - selected
        if right_distance >= left_distance and end - 1 > selected:
            end -= 1
        elif start < selected:
            start += 1
        else:
            break
    return start, end


def _grouped_line_count(
    entries: Sequence[LauncherEntry],
    *,
    start: int = 0,
    end: int | None = None,
) -> int:
    """Count rows, repeated headings, and separators in one grouped slice."""
    stop = len(entries) if end is None else end
    if start >= stop:
        return 0
    lines = 2  # The slice always starts with a Context heading and one row.
    for index in range(start + 1, stop):
        lines += 1 if entries[index].group == entries[index - 1].group else 3
    return lines


def _compact(value: str, width: int) -> str:
    """Compatibility wrapper around the shared terminal-cell policy."""

    return elide_terminal_text(display_escape_text(value), width)


def _pad_display(value: str, width: int) -> str:
    """Pad by terminal cells rather than code points for aligned CJK rows."""
    return pad_terminal_text(value, width)


def _render_entry_line(
    entry: LauncherEntry,
    *,
    entries: Sequence[LauncherEntry],
    selected: bool,
    available_width: int,
) -> str:
    """Render one row from the current viewport budget without fixed columns."""

    pointer = "›" if selected else " "
    # The timestamp is useful orientation on ordinary screens, but identity and
    # state take priority when a genuinely narrow terminal cannot hold all four
    # columns. Detail still exposes the complete timestamp for the selected row.
    timestamp = (
        f"{_format_timestamp(entry.sort_timestamp)}  "
        if available_width >= 64
        else ""
    )
    prefix = f"{pointer} {timestamp}"
    fixed_width = terminal_cell_width(prefix + "  [" + "]  ")
    field_budget = max(0, available_width - fixed_width)

    escaped_titles = tuple(display_escape_text(item.title) for item in entries)
    escaped_statuses = tuple(display_escape_text(item.status) for item in entries)
    escaped_summaries = tuple(display_escape_text(item.subtitle) for item in entries)
    title_natural = max((terminal_cell_width(value) for value in escaped_titles), default=0)
    status_natural = max(
        (terminal_cell_width(value) for value in escaped_statuses),
        default=0,
    )
    summary_natural = max(
        (terminal_cell_width(value) for value in escaped_summaries),
        default=0,
    )
    widths = allocate_adaptive_columns(
        field_budget,
        (
            AdaptiveColumn(
                "title",
                minimum=min(10, title_natural),
                preferred=title_natural,
                maximum=title_natural,
                shrink_order=1,
                grow_order=1,
            ),
            AdaptiveColumn(
                "status",
                minimum=min(6, status_natural),
                preferred=status_natural,
                maximum=status_natural,
                shrink_order=2,
                grow_order=0,
            ),
            AdaptiveColumn(
                "summary",
                minimum=min(10, summary_natural),
                preferred=summary_natural,
                shrink_order=0,
                grow_order=2,
                expand=True,
            ),
        ),
    )
    title = pad_terminal_text(
        elide_terminal_text(display_escape_text(entry.title), widths["title"]),
        widths["title"],
    )
    status = pad_terminal_text(
        elide_terminal_text(display_escape_text(entry.status), widths["status"]),
        widths["status"],
    )
    summary = elide_terminal_text(
        display_escape_text(entry.subtitle),
        widths["summary"],
    )
    line = f"{prefix}{title}  [{status}]  {summary}"
    return elide_terminal_text(line, available_width)


def _format_timestamp(value: float) -> str:
    """Use a deterministic UTC label while preserving numeric sort semantics."""
    return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def _detail_lines(value: str) -> tuple[str, ...]:
    lines = tuple(
        display_escape_text(line) for line in (value or "(no detail)").split("\n")
    )
    return (
        f" Detail       {lines[0]}",
        *(f"              {line}" for line in lines[1:]),
    )


def _render_detail(entry: LauncherEntry) -> str:
    """Render untrusted metadata without exposing the internal open receipt."""
    if entry.detail_only:
        return "\n".join(
            display_escape_text(line) for line in entry.detail.split("\n")
        )
    subtitle = entry.subtitle or "(none)"
    return "\n".join(
        (
            f" Kind         {display_escape_text(entry.kind)}",
            f" Key          {display_escape_text(entry.key)}",
            f" Title        {display_escape_text(entry.title)}",
            f" Status       {display_escape_text(entry.status)}",
            f" Context      {display_escape_text(entry.group)}",
            f" Modified     {_format_timestamp(entry.sort_timestamp)}",
            f" Summary      {display_escape_text(subtitle)}",
            *_detail_lines(entry.detail),
        )
    )


def _render_location(location: LauncherOrientation) -> str:
    """Render frozen store orientation without trusting terminal controls."""
    label_width = max(len(label) for label, _value in location.rows)
    return "\n".join(
        f" {display_escape_text(label).ljust(label_width)} · "
        f"{display_escape_text(value)}"
        for label, value in location.rows
    )


def _action_label(action: LauncherAction) -> str:
    return display_escape_text(action.label)


def _render_action_detail(action: LauncherAction) -> str:
    return "\n".join(
        (
            f" {_action_label(action)}",
            f" {display_escape_text(action.description)}",
        )
    )


def run_operation_launcher(
    spec: OperationLauncherSpec,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> LauncherSelection | None:
    """Select an entry or action identity without performing operation I/O.

    The operation adapter discovers and freezes the catalog before this call,
    then validates and interprets the returned identity afterwards. The
    launcher owns only process-local presentation state.
    """
    if not isinstance(spec, OperationLauncherSpec):
        raise TypeError("Operation launcher requires a typed specification.")
    options = spec.entries
    action = spec.action
    location = spec.orientation
    title = spec.title
    initial_sort_mode = spec.initial_sort_mode
    initial_group_mode = spec.initial_group_mode
    catalog_label = spec.catalog_label
    enter_action = spec.enter_action
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive operation launching requires a terminal. "
            "Pass an operation locator explicitly."
        )

    # Operations may choose the most legible initial projection, while S/G
    # still expose the same process-local alternatives. Ground begins grouped
    # because its saved work is interpreted relative to Contexts; the other
    # adapters retain the neutral recent/all defaults.
    state = _PickerState(
        sort_mode=initial_sort_mode,
        group_mode=initial_group_mode,
        new_selected=action is not None and not options,
    )
    windows: dict[str, Window] = {}
    bindings = KeyBindings()
    search_area = TextArea(
        height=1,
        prompt=[("class:search-label", " FILTER › ")],
        multiline=False,
        wrap_lines=False,
    )

    def current_options() -> tuple[LauncherEntry, ...]:
        projected = _ordered_entries(
            options,
            sort_mode=state.sort_mode,
            group_mode=state.group_mode,
            query=search_area.text,
        )
        state.selected_index = max(
            0,
            min(state.selected_index, max(0, len(projected) - 1)),
        )
        if not projected and action is not None:
            state.new_selected = True
        return projected

    def selected_identity() -> tuple[str, str] | None:
        projected = current_options()
        if not projected:
            return None
        return _entry_identity(projected[state.selected_index])

    def restore_selection(identity: tuple[str, str] | None) -> None:
        projected = current_options()
        if identity is None:
            state.selected_index = 0
            return
        for index, entry in enumerate(projected):
            if _entry_identity(entry) == identity:
                state.selected_index = index
                state.new_selected = False
                return
        state.selected_index = 0
        state.new_selected = action is not None and not projected

    def move(delta: int) -> None:
        projected = current_options()
        if state.new_selected:
            if delta > 0 and projected:
                state.new_selected = False
                state.selected_index = 0
            return
        if not projected:
            return
        if delta < 0 and state.selected_index == 0 and action is not None:
            state.new_selected = True
            if "detail" in windows:
                windows["detail"].vertical_scroll = 0
            return
        state.selected_index = max(
            0,
            min(state.selected_index + delta, len(projected) - 1),
        )
        if "detail" in windows:
            windows["detail"].vertical_scroll = 0

    def render_entries() -> list[tuple[str, str]]:
        projected = current_options()
        fragments: list[tuple[str, str]] = []
        available_width = live_window_content_width(
            windows.get("list"),
            fallback_reserved=1,
        )
        if action is not None:
            if state.new_selected:
                fragments.append(("[SetCursorPosition]", ""))
            pointer = "›" if state.new_selected else " "
            fragments.append(
                (
                    "class:selected" if state.new_selected else "class:new",
                    elide_terminal_text(
            f"{pointer} + {_action_label(action)}",
                        available_width,
                    ),
                )
            )
        if not projected:
            message = (
                f"No {display_escape_text(catalog_label)} yet."
                if not options and not search_area.text
                else f"No matching {display_escape_text(catalog_label)}."
            )
            if fragments:
                fragments.append(("", "\n"))
                fragments.append(("class:empty", f"  {message}"))
                return fragments
            return [("class:empty", f"  {message}")]
        if state.group_mode == "context":
            start, end = _visible_grouped_bounds(
                projected,
                state.selected_index,
                line_budget=(
                    _VISIBLE_ROWS - 1
                    if action is not None
                    else _VISIBLE_ROWS
                ),
            )
        else:
            start, end = _visible_bounds(
                state.selected_index,
                len(projected),
                line_budget=(
                    _VISIBLE_ROWS - 1
                    if action is not None
                    else _VISIBLE_ROWS
                ),
            )
        if fragments:
            fragments.append(("", "\n"))
        prior_group: str | None = None
        for index in range(start, end):
            entry = projected[index]
            if state.group_mode == "context" and entry.group != prior_group:
                if fragments:
                    fragments.append(("", "\n"))
                continued = (
                    index == start
                    and start > 0
                    and projected[start - 1].group == entry.group
                )
                suffix = " · CONTINUED" if continued else ""
                fragments.append(
                    (
                        "class:group",
                        elide_terminal_text(
                            "  CONTEXT · "
                            f"{display_escape_text(entry.group)}{suffix}",
                            available_width,
                        )
                        + "\n",
                    )
                )
                prior_group = entry.group
            selected = index == state.selected_index
            if selected:
                fragments.append(("[SetCursorPosition]", ""))
            line = _render_entry_line(
                entry,
                entries=projected[start:end],
                selected=selected,
                available_width=available_width,
            )
            fragments.append(("class:selected" if selected else "", line))
            if index < end - 1:
                fragments.append(("", "\n"))
        return fragments

    def render_detail() -> str:
        projected = current_options()
        if state.new_selected and action is not None:
            return _render_action_detail(action)
        if not projected:
            if not options and not search_area.text:
                suffix = (
                    f" Press N to {_action_label(action)}."
                    if action is not None
                    else " Start one with this operation's explicit operands."
                )
                return (
                    f" No {display_escape_text(catalog_label)} are available.\n"
                    + suffix
                )
            return (
                f" No {display_escape_text(catalog_label)} match the current filter.\n"
                " Clear or revise the filter, or press N when New is enabled."
            )
        return _render_detail(projected[state.selected_index])

    def render_header() -> str:
        sort_label = "RECENT FIRST" if state.sort_mode == "recent" else "NAME"
        group_label = "ALL" if state.group_mode == "all" else "BY CONTEXT"
        return f" {display_escape_text(title)} · {sort_label} · {group_label}"

    def render_footer() -> str:
        projected = current_options()
        total = len(projected) + (1 if action is not None else 0)
        if state.new_selected:
            position = f"1/{total}"
        elif projected:
            offset = 1 if action is not None else 0
            position = f"{state.selected_index + 1 + offset}/{total}"
        else:
            position = "0/0"
        new_hint = (
            f"  N {_action_label(action)}"
            if action is not None
            else ""
        )
        query_hint = (
            f"  · filter: {display_escape_text(search_area.text)}"
            if search_area.text and not state.search_active
            else ""
        )
        return (
            " ↑/↓ move  PgUp/PgDn detail  "
            f"Enter {display_escape_text(enter_action)}  "
            "S sort  G group  / filter"
            f"{new_hint}  Esc/q cancel  ·  {position}{query_hint}"
        )

    list_control = FormattedTextControl(
        text=render_entries,
        focusable=True,
        show_cursor=False,
    )
    detail_control = FormattedTextControl(
        text=render_detail,
        focusable=False,
        show_cursor=False,
    )

    list_focused = ~has_focus(search_area)

    @bindings.add("down", filter=list_focused)
    def _next_session(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=list_focused)
    def _previous_session(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("pagedown", filter=list_focused)
    def _scroll_detail_down(event) -> None:
        windows["detail"].vertical_scroll += 8
        event.app.invalidate()

    @bindings.add("pageup", filter=list_focused)
    def _scroll_detail_up(event) -> None:
        windows["detail"].vertical_scroll = max(
            0,
            windows["detail"].vertical_scroll - 8,
        )
        event.app.invalidate()

    @bindings.add("enter", filter=list_focused)
    def _open_session(event) -> None:
        if state.new_selected and action is not None:
            event.app.exit(result=LauncherActionSelection(action.uid))
            return
        projected = current_options()
        if not projected:
            return
        entry = projected[state.selected_index]
        event.app.exit(
            result=LauncherEntrySelection(
                kind=entry.kind,
                key=entry.key,
            )
        )

    @bindings.add("s", filter=list_focused)
    def _toggle_sort(event) -> None:
        keep_new = state.new_selected
        identity = selected_identity()
        state.sort_mode = "name" if state.sort_mode == "recent" else "recent"
        if not keep_new:
            restore_selection(identity)
        event.app.invalidate()

    @bindings.add("g", filter=list_focused)
    def _toggle_group(event) -> None:
        keep_new = state.new_selected
        identity = selected_identity()
        state.group_mode = "context" if state.group_mode == "all" else "all"
        if not keep_new:
            restore_selection(identity)
        event.app.invalidate()

    @bindings.add("/", filter=list_focused)
    def _start_filter(event) -> None:
        state.search_active = True
        state.search_before_edit = search_area.text
        event.app.layout.focus(search_area)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(search_area), eager=True)
    def _apply_filter(event) -> None:
        state.search_active = False
        state.selected_index = 0
        state.new_selected = action is not None and not current_options()
        event.app.layout.focus(list_control)
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(search_area), eager=True)
    def _cancel_filter_edit(event) -> None:
        search_area.text = state.search_before_edit
        state.search_active = False
        state.selected_index = 0
        state.new_selected = action is not None and not current_options()
        event.app.layout.focus(list_control)
        event.app.invalidate()

    if action is not None:

        @bindings.add("n", filter=list_focused)
        @bindings.add("N", filter=list_focused)
        def _new_session(event) -> None:
            event.app.exit(result=LauncherActionSelection(action.uid))

    @bind_case_insensitive_key(bindings, "q", filter=list_focused, eager=True)
    @bindings.add("escape", filter=list_focused, eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(render_header),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    location_window = ConditionalContainer(
        Window(
            FormattedTextControl(
                lambda: _render_location(location) if location is not None else ""
            ),
            height=Dimension.exact(2),
            dont_extend_height=True,
            wrap_lines=False,
        ),
        filter=Condition(lambda: location is not None),
    )
    grouped_catalog = _ordered_entries(
        options,
        sort_mode="recent",
        group_mode="context",
    )
    list_preferred_height = min(
        _VISIBLE_ROWS,
        max(
            2 if not options and action is not None else 1,
            len(options) + (1 if action is not None else 0),
            _grouped_line_count(grouped_catalog)
            + (1 if action is not None else 0),
        ),
    )
    list_window = Window(
        list_control,
        height=Dimension(
            min=1,
            preferred=list_preferred_height,
            max=_VISIBLE_ROWS + 4,
        ),
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    windows["list"] = list_window
    search_window = ConditionalContainer(
        search_area,
        filter=Condition(lambda: state.search_active or bool(search_area.text)),
    )
    detail_window = Window(
        detail_control,
        height=Dimension(min=5, preferred=10, weight=1),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    windows["detail"] = detail_window
    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[LauncherSelection | None] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    location_window,
                    horizontal_rule(),
                    list_window,
                    search_window,
                    horizontal_rule(),
                    detail_window,
                    horizontal_rule(),
                    footer,
                ]
            ),
            focused_element=list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=Style.from_dict(
            {
                "selected": "reverse bold",
                "group": "bold",
                "search-label": "bold",
                "empty": "italic",
                "new": "bold",
            }
        ),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
