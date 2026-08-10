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

from memcommit.commands.tui_primitives import (
    bind_case_insensitive_key,
    display_escape_text,
)


@dataclass(frozen=True)
class ProfilePickerEntry:
    """Display-only summary of one already validated Profile."""

    name: str
    context_count: int
    current_context: str | None
    memory_count: int = 0
    granted_context_count: int = 0
    granted_memory_count: int = 0
    query_source_count: int = 0
    query_source_names: tuple[str, ...] = ()
    study_name: str | None = None
    study_created_at: str | None = None
    study_task: int | None = None
    study_role: str | None = None


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
        or entry.memory_count < 0
        or entry.granted_context_count < 0
        or entry.granted_memory_count < 0
        or entry.query_source_count < 0
        or len(entry.query_source_names) > entry.query_source_count
        or any(not name for name in entry.query_source_names)
        or len(set(entry.query_source_names)) != len(entry.query_source_names)
        or (
            any(
                value is not None
                for value in (
                    entry.study_name,
                    entry.study_created_at,
                    entry.study_task,
                    entry.study_role,
                )
            )
            and not (
                isinstance(entry.study_name, str)
                and bool(entry.study_name)
                and isinstance(entry.study_created_at, str)
                and bool(entry.study_created_at)
                and (
                    (
                        type(entry.study_task) is int
                        and entry.study_task in {1, 2, 3}
                        and entry.study_role in {None, "TASK", "AUTHORITY"}
                    )
                    or (
                        entry.study_task is None
                        and entry.study_role
                        in {"PARTICIPANT", "GRANTED_MEMORY"}
                    )
                )
            )
        )
        for entry in options
    ) or len(set(names)) != len(names):
        raise ValueError("Profile selection received invalid entries.")
    study_metadata: dict[str, tuple[str, set[tuple[str, int | None]]]] = {}
    finished_studies: set[str] = set()
    previous_study: str | None = None
    for entry in options:
        study_name = entry.study_name
        if study_name is None:
            if previous_study is not None:
                finished_studies.add(previous_study)
            previous_study = None
            continue
        if previous_study is not None and study_name != previous_study:
            finished_studies.add(previous_study)
        if study_name in finished_studies:
            raise ValueError("Study Profile entries must remain contiguous.")
        created_at = entry.study_created_at
        task = entry.study_task
        assert isinstance(created_at, str)
        member = (entry.study_role or "TASK", task)
        existing = study_metadata.get(study_name)
        if existing is None:
            study_metadata[study_name] = (created_at, {member})
        elif existing[0] != created_at or member in existing[1]:
            raise ValueError("Study Profile entries are inconsistent.")
        else:
            existing[1].add(member)
        previous_study = study_name
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
    def entry_name_label(entry: ProfilePickerEntry) -> str:
        if entry.study_name is None:
            return display_escape_text(entry.name)
        if entry.study_role == "PARTICIPANT":
            role = "Participant"
        elif entry.study_role == "GRANTED_MEMORY":
            role = "Granted memory"
        else:
            role = f"{(entry.study_role or 'TASK').title()} {entry.study_task}"
        return f"{role} · {display_escape_text(entry.name)}"

    name_labels = tuple(entry_name_label(entry) for entry in options)
    name_width = min(max(max(len(label) for label in name_labels), 8), 24)
    fragments: list[tuple[str, str]] = []
    previous_study: str | None = None
    for index, entry in enumerate(options):
        if entry.study_name is not None and entry.study_name != previous_study:
            fragments.extend(
                [
                    (
                        "class:study",
                        "  STUDY "
                        + display_escape_text(entry.study_name)
                        + " · created="
                        + display_escape_text(entry.study_created_at or ""),
                    ),
                    ("", "\n"),
                ]
            )
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
                    f"  Contexts {entry.context_count} owned + "
                    f"{entry.granted_context_count} granted · "
                    f"Memories {entry.memory_count} owned + "
                    f"{entry.granted_memory_count} granted"
                    f"{query_note} · current={current_context}",
                ),
            ]
        )
        if index < len(options) - 1:
            fragments.append(("", "\n"))
        previous_study = entry.study_name
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

    @bind_case_insensitive_key(bindings, "q", eager=True)
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
                "study": "ansicyan bold",
            }
        ),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
