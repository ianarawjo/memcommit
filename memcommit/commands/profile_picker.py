"""Full-screen terminal picker for selecting or permanently deleting Profiles."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import sys
from typing import Literal

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
from prompt_toolkit.styles import Style, merge_styles

from memcommit.commands.background_turn import BackgroundExecutorTurn
from memcommit.commands.command_progress import (
    BUSY_INTERVAL_SECONDS,
    busy_suffix,
)
from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    render_exact_command_review,
)
from memcommit.interfaces.tui.components.exact_command_review import (
    bind_exact_command_approval,
)
from memcommit.commands.tui_primitives import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.interfaces.tui.core.theme import MEMCOMMIT_TUI_STYLE
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.profile_config import ProfileConfigError, validate_profile_name


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
    rename_block: str | None = None


@dataclass(frozen=True)
class ProfilePickerAction:
    """One exact selector action returned only after its required key path."""

    kind: Literal["USE", "RENAME_PROFILE", "REMOVE_PROFILE", "REMOVE_STUDY"]
    name: str
    uid: str | None
    registry_generation: int | None
    new_name: str | None = None
    row_index: int | None = None


@dataclass(frozen=True)
class ProfilePickerRefresh:
    """A completed picker mutation that requires a fresh Profile catalog."""

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
        or (entry.rename_block is not None and not entry.rename_block.strip())
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


def _rename_review(action: ProfilePickerAction) -> ExactCommandReview:
    """Render the exact Profile display-name mutation selected in the picker."""

    if action.kind != "RENAME_PROFILE" or action.new_name is None:
        raise ValueError("Profile rename review requires an exact new name.")
    return ExactCommandReview(
        argv=("mem", "profile", "rename", action.name, action.new_name),
        effects=(
            f"Change Profile {action.name!r}'s display name to {action.new_name!r}.",
            "Keep the same Profile UID, store directory, Contexts, Memories, and Grants.",
            "Keep the same active Profile selected when this Profile is current.",
        ),
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
    rename_target: dict[str, ProfilePickerAction | None] = {"action": None}
    status = {"text": initial_status}
    status_is_error = {"value": False}
    background_turn: BackgroundExecutorTurn[str] = BackgroundExecutorTurn(
        interval_seconds=_PROFILE_DELETION_BUSY_INTERVAL_SECONDS,
    )
    background_result: dict[str, ProfilePickerRefresh | None] = {"value": None}
    bindings = KeyBindings()
    review_mode = Condition(
        lambda: pending["action"] is not None and not background_turn.busy
    )
    rename_mode = Condition(
        lambda: rename_target["action"] is not None
        and pending["action"] is None
        and not background_turn.busy
    )
    picker_mode = Condition(
        lambda: pending["action"] is None
        and rename_target["action"] is None
        and not background_turn.busy
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
    rename_field = ExactNameFieldControl.create(
        ExactNameFieldView(
            value="",
            label="NEW PROFILE NAME",
            state="NEW NAME",
            detail="Enter to review this exact Profile rename.",
            validate=validate_profile_name,
            value_label="Profile name",
            # Profile names are exact one-segment identifiers; prompt padding
            # must not be normalized into a different registry key.
            strip_candidate=False,
        ),
        input_name="profile-picker-rename",
        frame_style="class:profile-rename-field",
    )

    def clear_stale_rename_error(_buffer) -> None:
        if rename_target["action"] is not None:
            status["text"] = ""
            status_is_error["value"] = False

    rename_field.input.buffer.on_text_changed += clear_stale_rename_error

    def move(delta: int) -> None:
        selected["index"] = max(
            0,
            min(selected["index"] + delta, len(rows) - 1),
        )
        status["text"] = ""
        status_is_error["value"] = False

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
            status_is_error["value"] = False
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

    @bind_case_insensitive_key(bindings, "r", filter=picker_mode, eager=True)
    def _edit_profile_name(event) -> None:
        row = current_row()
        if row.kind == "STUDY":
            status["text"] = "Study headers cannot be renamed here"
            status_is_error["value"] = True
            event.app.invalidate()
            return
        entry = row.entry
        assert entry is not None
        if entry.rename_block is not None:
            status["text"] = entry.rename_block
            status_is_error["value"] = True
            event.app.invalidate()
            return
        rename_target["action"] = ProfilePickerAction(
            kind="RENAME_PROFILE",
            name=row.name,
            uid=row.uid,
            registry_generation=registry_generation,
            row_index=selected["index"],
        )
        rename_field.set_text(row.name)
        status["text"] = ""
        status_is_error["value"] = False
        event.app.layout.focus(rename_field.input)
        event.app.invalidate()

    @bindings.add(
        "enter",
        filter=rename_mode & has_focus(rename_field.input),
        eager=True,
    )
    def _review_profile_name(event) -> None:
        try:
            new_name = rename_field.validate_candidate()
        except (ProfileConfigError, TypeError, ValueError) as error:
            status["text"] = display_escape_text(str(error))
            status_is_error["value"] = True
            event.app.invalidate()
            return
        target = rename_target["action"]
        assert isinstance(target, ProfilePickerAction)
        action = ProfilePickerAction(
            kind="RENAME_PROFILE",
            name=target.name,
            uid=target.uid,
            registry_generation=target.registry_generation,
            new_name=new_name,
            row_index=target.row_index,
        )
        pending["action"] = action
        pending["review"] = _rename_review(action)
        rename_target["action"] = None
        status["text"] = ""
        status_is_error["value"] = False
        event.app.layout.focus(control)
        event.app.invalidate()

    @bindings.add(
        "c-j",
        filter=rename_mode & has_focus(rename_field.input),
        eager=True,
    )
    def _reject_profile_name_newline(event) -> None:
        status["text"] = "Profile name must stay on one line"
        status_is_error["value"] = True
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "d", filter=picker_mode, eager=True)
    def _review_removal(event) -> None:
        row = current_row()
        if row.kind == "PROFILE":
            entry = row.entry
            assert entry is not None
            if row.name == current:
                status["text"] = "CURRENT Profile cannot be removed · switch first"
                status_is_error["value"] = True
                event.app.invalidate()
                return
            if entry.removal_block is not None:
                status["text"] = entry.removal_block
                status_is_error["value"] = True
                event.app.invalidate()
                return
        elif any(
            entry.study_name == row.name and entry.name == current
            for entry in options
        ):
            status["text"] = "Study contains CURRENT Profile · switch first"
            status_is_error["value"] = True
            event.app.invalidate()
            return
        action = _removal_action(
            row,
            registry_generation=registry_generation,
        )
        pending["action"] = action
        pending["review"] = _removal_review(action, row)
        status["text"] = ""
        status_is_error["value"] = False
        event.app.invalidate()

    @bind_exact_command_approval(bindings, filter=review_mode, eager=True)
    def _apply_reviewed_action(event) -> None:
        action = pending["action"]
        assert isinstance(action, ProfilePickerAction)
        reviewed_row_index = selected["index"]
        # Rename is a short registry mutation. Return its frozen receipt to the
        # Profile command so the picker is rebuilt from the next generation.
        if action.kind == "RENAME_PROFILE" or apply_removal is None:
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
            action = pending["action"]
            pending["action"] = None
            pending["review"] = None
            if (
                isinstance(action, ProfilePickerAction)
                and action.kind == "RENAME_PROFILE"
            ):
                rename_target["action"] = ProfilePickerAction(
                    kind="RENAME_PROFILE",
                    name=action.name,
                    uid=action.uid,
                    registry_generation=action.registry_generation,
                    row_index=action.row_index,
                )
                status["text"] = "Rename review cancelled"
                status_is_error["value"] = False
                event.app.layout.focus(rename_field.input)
            else:
                status["text"] = "Removal review cancelled"
                status_is_error["value"] = False
            event.app.invalidate()
            return
        if rename_target["action"] is not None:
            rename_target["action"] = None
            status["text"] = "Rename cancelled"
            status_is_error["value"] = False
            event.app.layout.focus(control)
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
        if rename_mode():
            action = rename_target["action"]
            assert isinstance(action, ProfilePickerAction)
            return " Rename Profile " + display_escape_text(action.name)
        return (
            (
                " Review exact Profile rename"
                if isinstance(pending["action"], ProfilePickerAction)
                and pending["action"].kind == "RENAME_PROFILE"
                else " Review irreversible deletion"
            )
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
            action = pending["action"]
            if (
                isinstance(action, ProfilePickerAction)
                and action.kind == "RENAME_PROFILE"
            ):
                return (
                    " Enter/A rename Profile  Esc back"
                )
            return (
                " Enter/A apply exact command  Esc back · IRREVERSIBLE · "
                "store and checkpoints will be deleted"
            )
        if rename_mode():
            message = status["text"]
            prefix = " Ctrl-U clear  Enter review exact command  Esc back"
            if not message:
                return prefix
            message_style = (
                "class:error"
                if status_is_error["value"]
                else "class:memcommit.notification"
            )
            return [("", prefix + " · "), (message_style, message)]
        row = current_row()
        action = (
            "D remove Study"
            if row.kind == "STUDY"
            else "Enter use  R rename  D remove Profile"
        )
        message = status["text"]
        prefix = (
            f" ↑/↓ move  {action}  Esc/q cancel"
            f"  ·  {selected['index'] + 1}/{len(rows)}"
        )
        if not message:
            return prefix
        message_style = (
            "class:error" if status_is_error["value"] else "class:success"
        )
        return [("", prefix + " · "), (message_style, message)]

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
                    ConditionalContainer(
                        content=HSplit(
                            [
                                Window(height=1, char="─"),
                                rename_field.frame,
                            ]
                        ),
                        filter=rename_mode,
                    ),
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
        style=merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                Style.from_dict(
                    {
                        "selected": "reverse bold",
                        "current": "ansigreen bold",
                        "study": "ansicyan bold",
                        "success": "ansigreen bold",
                        "error": "ansired bold",
                        "profile-rename-field": "fg:#f4f5f7",
                    }
                ),
            ]
        ),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
