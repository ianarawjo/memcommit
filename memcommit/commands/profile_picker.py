"""Full-screen terminal picker for selecting one MemoryStore profile."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import sys

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style

from memcommit.commands.tui_primitives import display_escape_text


@dataclass(frozen=True)
class ProfilePickerEntry:
    """Display-only summary of one already validated Profile."""

    name: str
    context_count: int
    current_context: str | None
    query_source_count: int = 0
    query_source_names: tuple[str, ...] = ()


def _validate_entries(
    entries: Sequence[ProfilePickerEntry],
    *,
    current: str,
) -> tuple[ProfilePickerEntry, ...]:
    options = tuple(entries)
    if not options:
        raise ValueError("No profiles are available to select.")
    names = [entry.name for entry in options]
    if any(
        not isinstance(entry.name, str)
        or not entry.name
        or entry.context_count < 0
        or entry.query_source_count < 0
        or len(entry.query_source_names) > entry.query_source_count
        or any(not name for name in entry.query_source_names)
        or len(set(entry.query_source_names)) != len(entry.query_source_names)
        for entry in options
    ) or len(set(names)) != len(names):
        raise ValueError("Profile selection received invalid entries.")
    if current not in names:
        raise ValueError("The current profile is not available to select.")
    return options


def _render_profile_options(
    entries: Sequence[ProfilePickerEntry],
    *,
    selected: int,
    current: str,
) -> list[tuple[str, str]]:
    """Render the persistent CURRENT row and selected USE action."""
    options = _validate_entries(entries, current=current)
    if selected < 0 or selected >= len(options):
        raise ValueError("Selected profile index is out of range.")
    name_labels = tuple(display_escape_text(entry.name) for entry in options)
    name_width = min(max(max(len(label) for label in name_labels), 8), 24)
    fragments: list[tuple[str, str]] = []
    for index, entry in enumerate(options):
        is_selected = index == selected
        is_current = entry.name == current
        if is_selected:
            # Keep the cursor attached to the selected row so prompt-toolkit
            # can scroll naturally at any terminal height.
            fragments.append(("[SetCursorPosition]", ""))
        row_style = "class:selected" if is_selected else ""
        pointer = "›" if is_selected else " "
        marker = "*" if is_current else " "
        action = "CURRENT" if is_current else ("USE" if is_selected else "")
        action_style = row_style or ("class:current" if is_current else "")
        # Raw entry values remain the selection identity.  Only labels passed
        # to prompt-toolkit are escaped into a single unambiguous terminal row.
        name_label = name_labels[index]
        current_context = (
            display_escape_text(entry.current_context)
            if entry.current_context
            else "(none)"
        )
        query_note = (
            " · query="
            + ",".join(display_escape_text(name) for name in entry.query_source_names)
            if entry.query_source_names
            else (
                f" · {entry.query_source_count} query-only"
                if entry.query_source_count
                else ""
            )
        )
        fragments.extend(
            [
                (row_style, f"{pointer} {marker} {name_label:<{name_width}}  "),
                (action_style, f"{action:<7}"),
                (
                    row_style,
                    f"  {entry.context_count} Contexts"
                    f"{query_note} · current={current_context}",
                ),
            ]
        )
        if index < len(options) - 1:
            fragments.append(("", "\n"))
    return fragments


def choose_profile(
    entries: Sequence[ProfilePickerEntry],
    *,
    current: str,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Return the selected Profile name, or ``None`` when cancelled."""
    options = _validate_entries(entries, current=current)
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive profile selection requires a terminal. "
            "Pass a profile name explicitly."
        )

    selected = {
        "index": next(
            index for index, entry in enumerate(options) if entry.name == current
        )
    }
    bindings = KeyBindings()

    def render_options():
        return _render_profile_options(
            options,
            selected=selected["index"],
            current=current,
        )

    control = FormattedTextControl(
        text=render_options,
        focusable=True,
        show_cursor=False,
    )

    def move(delta: int) -> None:
        selected["index"] = max(
            0,
            min(selected["index"] + delta, len(options) - 1),
        )

    @bindings.add("down")
    def _next_profile(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up")
    def _previous_profile(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("enter")
    def _accept_profile(event) -> None:
        event.app.exit(result=options[selected["index"]].name)

    @bindings.add("q", eager=True)
    @bindings.add("escape")
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(" Select a Profile"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                " ↑/↓ move  Enter use  Esc/q cancel"
                f"  ·  {selected['index'] + 1}/{len(options)}"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[str | None] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    Window(height=1, char="─"),
                    options_window,
                    Window(height=1, char="─"),
                    footer,
                ]
            ),
            focused_element=control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=Style.from_dict(
            {
                "selected": "reverse bold",
                "current": "ansigreen bold",
            }
        ),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
