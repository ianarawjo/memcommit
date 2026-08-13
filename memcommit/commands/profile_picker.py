"""Full-screen terminal picker for selecting or permanently deleting Profiles."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import sys
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style

from memcommit.commands.background_turn import BackgroundExecutorTurn
from memcommit.commands.command_progress import (
    BUSY_INTERVAL_SECONDS,
    busy_suffix,
)
from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    render_exact_command_review,
)
from memcommit.commands.tui_primitives import (
    bind_case_insensitive_key,
    display_escape_text,
)


@dataclass(frozen=True)
class ProfilePickerEntry:
    """Display-only summary of one already validated visible Profile."""

    name: str
    context_count: int
    current_context: str | None
    memory_count: int = 0
    granted_context_count: int = 0
    granted_memory_count: int = 0
    query_source_count: int = 0
    query_source_names: tuple[str, ...] = ()
    uid: str | None = None
    study_uid: str | None = None
    study_name: str | None = None
    study_created_at: str | None = None
    study_task: int | None = None
    study_role: str | None = None
    study_profile_count: int = 0
    study_removed_count: int = 0
    removal_block: str | None = None


@dataclass(frozen=True)
class ProfilePickerAction:
    """One exact selector action returned only after its required key path."""

    kind: Literal["USE", "REMOVE_PROFILE", "REMOVE_STUDY"]
    name: str
    uid: str | None
    registry_generation: int | None


@dataclass(frozen=True)
class ProfilePickerRefresh:
    """A completed background deletion that requires a fresh picker catalog."""

    status: str
    error: Exception | None = None
    close_requested: bool = False
    preferred_row_index: int | None = None


@dataclass(frozen=True)
class _ProfilePickerRow:
    kind: Literal["PROFILE", "STUDY"]
    name: str
    uid: str | None
    entry: ProfilePickerEntry | None = None
    created_at: str | None = None
    profile_count: int = 1
    removed_count: int = 0


_PROFILE_DELETION_BUSY_INTERVAL_SECONDS = BUSY_INTERVAL_SECONDS


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
        or (entry.uid is not None and not entry.uid)
        or (entry.removal_block is not None and not entry.removal_block.strip())
        or (
            any(
                value is not None
                for value in (
                    entry.study_uid,
                    entry.study_name,
                    entry.study_created_at,
                    entry.study_task,
                    entry.study_role,
                )
            )
            and not (
                isinstance(entry.study_uid, str)
                and bool(entry.study_uid)
                and isinstance(entry.study_name, str)
                and bool(entry.study_name)
                and isinstance(entry.study_created_at, str)
                and bool(entry.study_created_at)
                and entry.study_profile_count > 0
                and 0 <= entry.study_removed_count < entry.study_profile_count
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
        or (
            entry.study_name is None
            and (entry.study_profile_count != 0 or entry.study_removed_count != 0)
        )
        for entry in options
    ) or len(set(names)) != len(names):
        raise ValueError("Profile selection received invalid entries.")
    study_metadata: dict[
        str,
        tuple[str, str, int, int, set[tuple[str, int | None]]],
    ] = {}
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
        study_uid = entry.study_uid
        task = entry.study_task
        assert isinstance(created_at, str)
        assert isinstance(study_uid, str)
        member = (entry.study_role or "TASK", task)
        existing = study_metadata.get(study_name)
        metadata = (
            study_uid,
            created_at,
            entry.study_profile_count,
            entry.study_removed_count,
        )
        if existing is None:
            study_metadata[study_name] = (*metadata, {member})
        elif existing[:4] != metadata or member in existing[4]:
            raise ValueError("Study Profile entries are inconsistent.")
        else:
            existing[4].add(member)
        previous_study = study_name
    if current not in names:
        raise ValueError("The current profile is not available to select.")
    return options


def _picker_rows(
    entries: Sequence[ProfilePickerEntry],
    *,
    current: str,
) -> tuple[_ProfilePickerRow, ...]:
    options = _validate_entries(entries, current=current)
    rows: list[_ProfilePickerRow] = []
    previous_study: str | None = None
    for entry in options:
        if entry.study_name is not None and entry.study_name != previous_study:
            rows.append(
                _ProfilePickerRow(
                    kind="STUDY",
                    name=entry.study_name,
                    uid=entry.study_uid,
                    created_at=entry.study_created_at,
                    profile_count=entry.study_profile_count,
                    removed_count=entry.study_removed_count,
                )
            )
        rows.append(
            _ProfilePickerRow(
                kind="PROFILE",
                name=entry.name,
                uid=entry.uid,
                entry=entry,
            )
        )
        previous_study = entry.study_name
    return tuple(rows)


def _entry_name_label(entry: ProfilePickerEntry) -> str:
    if entry.study_name is None:
        return display_escape_text(entry.name)
    if entry.study_role == "PARTICIPANT":
        role = "Participant"
    elif entry.study_role == "GRANTED_MEMORY":
        role = "Granted memory"
    else:
        role = f"{(entry.study_role or 'TASK').title()} {entry.study_task}"
    return f"{role} · {display_escape_text(entry.name)}"


def _render_profile_options(
    entries: Sequence[ProfilePickerEntry],
    *,
    selected: int,
    current: str,
) -> list[tuple[str, str]]:
    """Render Study headers and Profile children as peer keyboard rows."""

    options = _validate_entries(entries, current=current)
    rows = _picker_rows(options, current=current)
    if selected < 0 or selected >= len(rows):
        raise ValueError("Selected profile row index is out of range.")
    name_width = min(
        max(max(len(_entry_name_label(entry)) for entry in options), 8),
        24,
    )
    fragments: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        is_selected = index == selected
        if is_selected:
            fragments.append(("[SetCursorPosition]", ""))
        pointer = "›" if is_selected else " "
        row_style = "class:selected" if is_selected else ""
        if row.kind == "STUDY":
            active_count = row.profile_count - row.removed_count
            count_label = f"{active_count} active"
            if row.removed_count:
                count_label += f" · {row.removed_count} removed"
            fragments.append(
                (
                    row_style or "class:study",
                    f"{pointer} STUDY {display_escape_text(row.name)} · "
                    f"{count_label} · created="
                    f"{display_escape_text(row.created_at or '')}",
                )
            )
        else:
            entry = row.entry
            assert entry is not None
            is_current = entry.name == current
            marker = "*" if is_current else " "
            action = "CURRENT" if is_current else ("USE" if is_selected else "")
            action_style = row_style or ("class:current" if is_current else "")
            current_context = (
                display_escape_text(entry.current_context)
                if entry.current_context
                else "(none)"
            )
            query_note = (
                " · query="
                + ",".join(
                    display_escape_text(name) for name in entry.query_source_names
                )
                if entry.query_source_names
                else (
                    f" · {entry.query_source_count} query-only"
                    if entry.query_source_count
                    else ""
                )
            )
            fragments.extend(
                [
                    (
                        row_style,
                        f"{pointer} {marker} {_entry_name_label(entry):<{name_width}}  ",
                    ),
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
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments


def _removal_action(
    row: _ProfilePickerRow,
    *,
    registry_generation: int | None,
) -> ProfilePickerAction:
    return ProfilePickerAction(
        kind="REMOVE_STUDY" if row.kind == "STUDY" else "REMOVE_PROFILE",
        name=row.name,
        uid=row.uid,
        registry_generation=registry_generation,
    )


def _removal_review(
    action: ProfilePickerAction,
    row: _ProfilePickerRow,
) -> ExactCommandReview:
    if action.kind == "REMOVE_STUDY":
        effects = (
            f"Permanently delete all {row.profile_count} Profile stores in "
            f"Study {row.name!r}.",
            "Delete every Memory, session, and checkpoint in those stores.",
            "Remove every Grant connected to those Profiles.",
            "This cannot be undone or recovered by mem.",
        )
        command = "remove-study"
    else:
        entry = row.entry
        assert entry is not None
        effects_list = [
            f"Permanently delete only Profile {row.name!r} and its store.",
            "Delete every Memory, session, and checkpoint in that store.",
            "Remove every Grant connected to this Profile.",
            "This cannot be undone or recovered by mem.",
        ]
        if entry.study_name is not None:
            effects_list.append(
                f"Keep Study {entry.study_name!r} and its other Profile rows."
            )
        effects = tuple(effects_list)
        command = "remove"
    return ExactCommandReview(
        argv=("mem", "profile", command, action.name, "--force"),
        effects=effects,
    )


def choose_profile(
    entries: Sequence[ProfilePickerEntry],
    *,
    current: str,
    registry_generation: int | None = None,
    initial_status: str = "",
    initial_row_index: int | None = None,
    apply_removal: Callable[[ProfilePickerAction], str] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ProfilePickerAction | ProfilePickerRefresh | None:
    """Return one selected action, or ``None`` when cancelled."""

    options = _validate_entries(entries, current=current)
    if not isinstance(initial_status, str):
        raise ValueError("Profile selection status must be text.")
    if initial_row_index is not None and (
        not isinstance(initial_row_index, int)
        or isinstance(initial_row_index, bool)
        or initial_row_index < 0
    ):
        raise ValueError("Profile selection row must be a nonnegative integer.")
    if apply_removal is not None and not callable(apply_removal):
        raise ValueError("Profile removal handler must be callable.")
    rows = _picker_rows(options, current=current)
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive profile selection requires a terminal. "
            "Pass a profile name explicitly."
        )

    current_index = next(
        index
        for index, row in enumerate(rows)
        if row.kind == "PROFILE" and row.name == current
    )
    selected = {
        # The same visual position resolves to the next surviving row after a
        # deletion, or the preceding row when the removed target was last.
        "index": (
            min(initial_row_index, len(rows) - 1)
            if initial_row_index is not None
            else current_index
        )
    }
    pending: dict[str, object | None] = {"action": None, "review": None}
    status = {"text": initial_status}
    background_turn: BackgroundExecutorTurn[str] = BackgroundExecutorTurn(
        interval_seconds=_PROFILE_DELETION_BUSY_INTERVAL_SECONDS,
    )
    background_result: dict[str, ProfilePickerRefresh | None] = {"value": None}
    bindings = KeyBindings()
    review_mode = Condition(
        lambda: pending["action"] is not None and not background_turn.busy
    )
    picker_mode = Condition(
        lambda: pending["action"] is None and not background_turn.busy
    )

    def current_row() -> _ProfilePickerRow:
        return rows[selected["index"]]

    def render_content():
        review = pending["review"]
        if isinstance(review, ExactCommandReview):
            return [("", render_exact_command_review(review))]
        return _render_profile_options(
            options,
            selected=selected["index"],
            current=current,
        )

    control = FormattedTextControl(
        text=render_content,
        focusable=True,
        show_cursor=False,
    )

    def move(delta: int) -> None:
        selected["index"] = max(
            0,
            min(selected["index"] + delta, len(rows) - 1),
        )
        status["text"] = ""

    @bindings.add("down", filter=picker_mode)
    def _next_row(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=picker_mode)
    def _previous_row(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("enter", filter=picker_mode)
    def _accept_profile(event) -> None:
        row = current_row()
        if row.kind == "STUDY":
            status["text"] = "Study header selected · D reviews whole-Study removal"
            event.app.invalidate()
            return
        event.app.exit(
            result=ProfilePickerAction(
                kind="USE",
                name=row.name,
                uid=row.uid,
                registry_generation=registry_generation,
            )
        )

    @bind_case_insensitive_key(bindings, "d", filter=picker_mode, eager=True)
    def _review_removal(event) -> None:
        row = current_row()
        if row.kind == "PROFILE":
            entry = row.entry
            assert entry is not None
            if row.name == current:
                status["text"] = "CURRENT Profile cannot be removed · switch first"
                event.app.invalidate()
                return
            if entry.removal_block is not None:
                status["text"] = entry.removal_block
                event.app.invalidate()
                return
        elif any(
            entry.study_name == row.name and entry.name == current
            for entry in options
        ):
            status["text"] = "Study contains CURRENT Profile · switch first"
            event.app.invalidate()
            return
        action = _removal_action(
            row,
            registry_generation=registry_generation,
        )
        pending["action"] = action
        pending["review"] = _removal_review(action, row)
        status["text"] = ""
        event.app.invalidate()

    @bindings.add("enter", filter=review_mode, eager=True)
    @bind_case_insensitive_key(bindings, "a", filter=review_mode, eager=True)
    def _apply_reviewed_removal(event) -> None:
        action = pending["action"]
        assert isinstance(action, ProfilePickerAction)
        reviewed_row_index = selected["index"]
        if apply_removal is None:
            event.app.exit(result=action)
            return

        def work() -> str:
            return apply_removal(action)

        def on_success(message: str) -> None:
            background_result["value"] = ProfilePickerRefresh(
                status=message,
                preferred_row_index=reviewed_row_index,
            )

        def on_error(error: Exception) -> None:
            background_result["value"] = ProfilePickerRefresh(
                status="",
                error=error,
                preferred_row_index=reviewed_row_index,
            )

        def finish(*, close_requested: bool) -> None:
            result = background_result["value"]
            if result is None:
                result = ProfilePickerRefresh(
                    status="",
                    error=RuntimeError("Profile deletion finished without a result."),
                )
            event.app.exit(
                result=ProfilePickerRefresh(
                    status=result.status,
                    error=result.error,
                    close_requested=close_requested,
                    preferred_row_index=result.preferred_row_index,
                )
            )

        background_turn.start(
            event.app,
            work=work,
            on_success=on_success,
            on_error=on_error,
            on_idle=lambda: finish(close_requested=False),
            on_close=lambda: finish(close_requested=True),
        )
        event.app.invalidate()

    @bindings.add("escape")
    def _back_or_cancel(event) -> None:
        if background_turn.request_close():
            status["text"] = "Close requested · deletion will finish first"
            event.app.invalidate()
            return
        if pending["action"] is not None:
            pending["action"] = None
            pending["review"] = None
            status["text"] = "Removal review cancelled"
            event.app.invalidate()
            return
        event.app.exit(result=None)

    @bind_case_insensitive_key(bindings, "q", filter=picker_mode, eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        if background_turn.request_close():
            status["text"] = "Close requested · deletion will finish first"
            event.app.invalidate()
            return
        event.app.exit(result=None)

    def header_text() -> str:
        if background_turn.busy:
            action = pending["action"]
            assert isinstance(action, ProfilePickerAction)
            target_kind = "Study" if action.kind == "REMOVE_STUDY" else "Profile"
            return (
                f" Permanently deleting {target_kind} "
                f"{busy_suffix(background_turn.frame)}"
            )
        return (
            " Review irreversible deletion"
            if review_mode()
            else " Select a Profile or Study"
        )

    def footer_text() -> str:
        if background_turn.busy:
            close_note = (
                " · close requested"
                if background_turn.close_requested
                else " · Esc/Ctrl-C closes after deletion"
            )
            return (
                " DELETING STORE AND CHECKPOINTS "
                + busy_suffix(background_turn.frame)
                + close_note
            )
        if review_mode():
            return (
                " Enter/A apply exact command  Esc back · IRREVERSIBLE · "
                "store and checkpoints will be deleted"
            )
        row = current_row()
        action = "D remove Study" if row.kind == "STUDY" else "Enter use  D remove Profile"
        message = status["text"]
        prefix = (
            f" ↑/↓ move  {action}  Esc/q cancel"
            f"  ·  {selected['index'] + 1}/{len(rows)}"
        )
        if not message:
            return prefix
        return [("", prefix + " · "), ("class:success", message)]

    header = Window(
        FormattedTextControl(header_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[
        ProfilePickerAction | ProfilePickerRefresh | None
    ] = Application(
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
                "success": "ansigreen bold",
            }
        ),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
