"""Operation-neutral terminal picker for reopening persisted work sessions.

The picker receives a frozen presentation catalog and returns a local
selection receipt.  Catalog discovery, freshness validation, persistence, provider
calls, and command execution deliberately remain responsibilities of the
operation adapter.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, TypeAlias

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
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import TextArea

from memcommit.commands.tui_primitives import display_escape_text, horizontal_rule


SessionSortMode = Literal["recent", "name"]
SessionGroupMode = Literal["all", "context"]
_VISIBLE_ROWS = 12


def _validate_argv(value: tuple[str, ...], *, label: str) -> None:
    if (
        not isinstance(value, tuple)
        or not value
        or any(not isinstance(argument, str) for argument in value)
        or not value[0]
    ):
        raise ValueError(f"{label} must be a non-empty tuple of text arguments.")


@dataclass(frozen=True)
class SessionPickerEntry:
    """Validated presentation-only projection of one resumable session."""

    kind: str
    key: str
    title: str
    status: str
    subtitle: str
    group: str
    sort_timestamp: float
    detail: str
    # This is a display-only public route hint.  It can help a person recognize
    # the selected work, but it is never authoritative: some operations do not
    # expose a public command that identifies one immutable saved artifact.
    # Adapters must reopen by ``key`` and revalidate persisted identity instead.
    reopen_argv: tuple[str, ...]
    # Compare uses the detail pane as the report itself. Other adapters retain
    # the shared metadata envelope and public route hint.
    detail_only: bool = False

    def __post_init__(self) -> None:
        for label, value in (
            ("session kind", self.kind),
            ("session key", self.key),
            ("session title", self.title),
            ("session status", self.status),
            ("session group", self.group),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{label} must be non-empty text.")
        for label, value in (
            ("session subtitle", self.subtitle),
            ("session detail", self.detail),
        ):
            if not isinstance(value, str):
                raise ValueError(f"{label} must be text.")
        if not isinstance(self.detail_only, bool):
            raise ValueError("session detail-only mode must be boolean.")
        if (
            isinstance(self.sort_timestamp, bool)
            or not isinstance(self.sort_timestamp, (int, float))
            or not math.isfinite(self.sort_timestamp)
        ):
            raise ValueError("session sort timestamp must be finite numeric time.")
        try:
            datetime.fromtimestamp(self.sort_timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            raise ValueError(
                "session sort timestamp must be renderable UTC time."
            ) from error
        _validate_argv(self.reopen_argv, label="session reopen argv")


@dataclass(frozen=True)
class SessionOpenReceipt:
    """Local selection receipt for one frozen catalog entry."""

    kind: str
    key: str
    argv: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("open receipt kind must be non-empty text.")
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("open receipt key must be non-empty text.")
        _validate_argv(self.argv, label="open receipt argv")


@dataclass(frozen=True)
class SessionNewReceipt:
    """Exact command receipt supplied by an adapter for its new-session path."""

    kind: str
    argv: tuple[str, ...]
    action_label: str | None = None
    action_description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("new receipt kind must be non-empty text.")
        _validate_argv(self.argv, label="new receipt argv")
        for label, value in (
            ("new receipt action label", self.action_label),
            ("new receipt action description", self.action_description),
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or any(character in value for character in "\r\n")
            ):
                raise ValueError(f"{label} must be non-empty single-line text.")


SessionPickerReceipt: TypeAlias = SessionOpenReceipt | SessionNewReceipt


@dataclass(frozen=True)
class SessionPickerLocation:
    """Frozen store orientation supplied by an operation adapter."""

    profile_name: str
    store_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.profile_name, str) or not self.profile_name:
            raise ValueError("session picker profile name must be non-empty text.")
        if not isinstance(self.store_path, str) or not self.store_path:
            raise ValueError("session picker store path must be non-empty text.")


@dataclass
class _PickerState:
    selected_index: int = 0
    new_selected: bool = False
    sort_mode: SessionSortMode = "recent"
    group_mode: SessionGroupMode = "all"
    search_active: bool = False
    search_before_edit: str = ""


def _entry_identity(entry: SessionPickerEntry) -> tuple[str, str]:
    return entry.kind, entry.key


def _matches_filter(entry: SessionPickerEntry, query: str) -> bool:
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
    entries: Sequence[SessionPickerEntry],
    *,
    sort_mode: SessionSortMode,
    group_mode: SessionGroupMode,
    query: str = "",
) -> tuple[SessionPickerEntry, ...]:
    """Return one deterministic projection without changing the catalog."""
    filtered = [entry for entry in entries if _matches_filter(entry, query)]

    def recent_key(entry: SessionPickerEntry) -> tuple[object, ...]:
        return (
            -float(entry.sort_timestamp),
            entry.title.casefold(),
            entry.kind.casefold(),
            entry.key,
        )

    def name_key(entry: SessionPickerEntry) -> tuple[object, ...]:
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
    entries: Sequence[SessionPickerEntry],
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
    entries: Sequence[SessionPickerEntry],
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
    escaped = display_escape_text(value)
    if get_cwidth(escaped) <= width:
        return escaped
    kept: list[str] = []
    used = 0
    for character in escaped:
        character_width = get_cwidth(character)
        if used + character_width > width - 1:
            break
        kept.append(character)
        used += character_width
    return "".join(kept).rstrip() + "…"


def _pad_display(value: str, width: int) -> str:
    """Pad by terminal cells rather than code points for aligned CJK rows."""
    return value + (" " * max(0, width - get_cwidth(value)))


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


def _render_detail(entry: SessionPickerEntry) -> str:
    """Render untrusted metadata and each route-hint element visibly escaped."""
    if entry.detail_only:
        return "\n".join(
            display_escape_text(line) for line in entry.detail.split("\n")
        )
    argv_lines = tuple(
        f"   [{index}] {display_escape_text(argument)}"
        for index, argument in enumerate(entry.reopen_argv)
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
            " Public route hint · NOT EXECUTED",
            *argv_lines,
        )
    )


def _render_location(location: SessionPickerLocation) -> str:
    """Render frozen store orientation without trusting terminal controls."""
    return "\n".join(
        (
            f" PROFILE · {display_escape_text(location.profile_name)}",
            f" STORE   · {display_escape_text(location.store_path)}",
        )
    )


def _new_session_label(receipt: SessionNewReceipt) -> str:
    """Return the operation-specific label for the pinned launcher row."""

    if receipt.action_label is not None:
        return display_escape_text(receipt.action_label)
    operation = receipt.kind.replace("_", " ").replace("-", " ").title()
    return f"Add new {display_escape_text(operation)} session"


def _render_new_detail(receipt: SessionNewReceipt) -> str:
    argv_lines = tuple(
        f"   [{index}] {display_escape_text(argument)}"
        for index, argument in enumerate(receipt.argv)
    )
    return "\n".join(
        (
            f" {_new_session_label(receipt)}",
            " "
            + (
                display_escape_text(receipt.action_description)
                if receipt.action_description is not None
                else "Leave saved-session browsing and enter operation-specific setup."
            ),
            (
                " Exact action route · NOT EXECUTED"
                if receipt.action_label is not None
                else " Exact new-session route · NOT EXECUTED"
            ),
            *argv_lines,
        )
    )


def choose_session(
    entries: Sequence[SessionPickerEntry],
    *,
    title: str,
    new_receipt: SessionNewReceipt | None = None,
    location: SessionPickerLocation | None = None,
    initial_sort_mode: SessionSortMode = "recent",
    initial_group_mode: SessionGroupMode = "all",
    catalog_label: str = "saved sessions",
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SessionPickerReceipt | None:
    """Select a reopen/new receipt without performing any session I/O.

    The operation adapter must discover the catalog before this call and must
    validate and execute a returned receipt after this call.  This function
    only changes process-local presentation state.
    """
    options = tuple(entries)
    if not isinstance(title, str) or not title:
        raise ValueError("Session picker title must be non-empty text.")
    if any(not isinstance(entry, SessionPickerEntry) for entry in options):
        raise ValueError("Session picker received an invalid entry.")
    identities = tuple(_entry_identity(entry) for entry in options)
    if len(set(identities)) != len(identities):
        raise ValueError("Session picker received duplicate kind/key entries.")
    if new_receipt is not None and not isinstance(new_receipt, SessionNewReceipt):
        raise ValueError("Session picker received an invalid new receipt.")
    if location is not None and not isinstance(location, SessionPickerLocation):
        raise ValueError("Session picker received an invalid location.")
    if initial_sort_mode not in ("recent", "name"):
        raise ValueError("Session picker received an invalid initial sort mode.")
    if initial_group_mode not in ("all", "context"):
        raise ValueError("Session picker received an invalid initial group mode.")
    if (
        not isinstance(catalog_label, str)
        or not catalog_label
        or any(character in catalog_label for character in "\r\n")
    ):
        raise ValueError("Session picker catalog label must be non-empty text.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive session selection requires a terminal. "
            "Pass a session identifier explicitly."
        )

    # Operations may choose the most legible initial projection, while S/G
    # still expose the same process-local alternatives. Ground begins grouped
    # because its saved work is interpreted relative to Contexts; the other
    # adapters retain the neutral recent/all defaults.
    state = _PickerState(
        sort_mode=initial_sort_mode,
        group_mode=initial_group_mode,
        new_selected=new_receipt is not None and not options,
    )
    windows: dict[str, Window] = {}
    bindings = KeyBindings()
    search_area = TextArea(
        height=1,
        prompt=[("class:search-label", " FILTER › ")],
        multiline=False,
        wrap_lines=False,
    )

    def current_options() -> tuple[SessionPickerEntry, ...]:
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
        if not projected and new_receipt is not None:
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
        state.new_selected = new_receipt is not None and not projected

    def move(delta: int) -> None:
        projected = current_options()
        if state.new_selected:
            if delta > 0 and projected:
                state.new_selected = False
                state.selected_index = 0
            return
        if not projected:
            return
        if delta < 0 and state.selected_index == 0 and new_receipt is not None:
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
        if new_receipt is not None:
            if state.new_selected:
                fragments.append(("[SetCursorPosition]", ""))
            pointer = "›" if state.new_selected else " "
            fragments.append(
                (
                    "class:selected" if state.new_selected else "class:new",
                    f"{pointer} + {_new_session_label(new_receipt)}",
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
                    if new_receipt is not None
                    else _VISIBLE_ROWS
                ),
            )
        else:
            start, end = _visible_bounds(
                state.selected_index,
                len(projected),
                line_budget=(
                    _VISIBLE_ROWS - 1
                    if new_receipt is not None
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
                        "  CONTEXT · "
                        f"{display_escape_text(entry.group)}{suffix}\n",
                    )
                )
                prior_group = entry.group
            selected = index == state.selected_index
            if selected:
                fragments.append(("[SetCursorPosition]", ""))
            pointer = "›" if selected else " "
            title = _pad_display(_compact(entry.title, 30), 30)
            line = (
                f"{pointer} {_format_timestamp(entry.sort_timestamp)}  "
                f"{title}  "
                f"[{_compact(entry.status, 12)}]  "
                f"{_compact(entry.subtitle, 38)}"
            )
            fragments.append(("class:selected" if selected else "", line))
            if index < end - 1:
                fragments.append(("", "\n"))
        return fragments

    def render_detail() -> str:
        projected = current_options()
        if state.new_selected and new_receipt is not None:
            return _render_new_detail(new_receipt)
        if not projected:
            if not options and not search_area.text:
                suffix = (
                    f" Press N to {_new_session_label(new_receipt)}."
                    if new_receipt is not None
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
        total = len(projected) + (1 if new_receipt is not None else 0)
        if state.new_selected:
            position = f"1/{total}"
        elif projected:
            offset = 1 if new_receipt is not None else 0
            position = f"{state.selected_index + 1 + offset}/{total}"
        else:
            position = "0/0"
        new_hint = (
            f"  N {_new_session_label(new_receipt)}"
            if new_receipt is not None
            else ""
        )
        query_hint = (
            f"  · filter: {display_escape_text(search_area.text)}"
            if search_area.text and not state.search_active
            else ""
        )
        return (
            " ↑/↓ move  PgUp/PgDn detail  Enter open  S sort  G group  / filter"
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
        if state.new_selected and new_receipt is not None:
            event.app.exit(result=new_receipt)
            return
        projected = current_options()
        if not projected:
            return
        entry = projected[state.selected_index]
        event.app.exit(
            result=SessionOpenReceipt(
                kind=entry.kind,
                key=entry.key,
                argv=entry.reopen_argv,
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
        state.new_selected = new_receipt is not None and not current_options()
        event.app.layout.focus(list_control)
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(search_area), eager=True)
    def _cancel_filter_edit(event) -> None:
        search_area.text = state.search_before_edit
        state.search_active = False
        state.selected_index = 0
        state.new_selected = new_receipt is not None and not current_options()
        event.app.layout.focus(list_control)
        event.app.invalidate()

    if new_receipt is not None:

        @bindings.add("n", filter=list_focused)
        @bindings.add("N", filter=list_focused)
        def _new_session(event) -> None:
            event.app.exit(result=new_receipt)

    @bindings.add("q", filter=list_focused, eager=True)
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
            2 if not options and new_receipt is not None else 1,
            len(options) + (1 if new_receipt is not None else 0),
            _grouped_line_count(grouped_catalog)
            + (1 if new_receipt is not None else 0),
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
    app: Application[SessionPickerReceipt | None] = Application(
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
