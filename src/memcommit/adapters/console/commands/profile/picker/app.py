"""Wire Profile picker input, presentation, and reviewed execution callbacks."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import replace

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.profile.picker.model import (
    ProfilePickerAction,
    ProfilePickerEntry,
    ProfilePickerRefresh,
)
from memcommit.adapters.console.commands.profile.picker.presentation import (
    ProfilePickerView,
)
from memcommit.adapters.console.commands.profile.picker.rows import build_picker_rows
from memcommit.adapters.console.commands.profile.picker.state import ProfilePickerState
from memcommit.adapters.console.terminal.components.background_turn import (
    BackgroundExecutorTurn,
)
from memcommit.adapters.console.terminal.components.command_editor import (
    bind_exact_command_approval,
)
from memcommit.adapters.console.terminal.components.progress import (
    BUSY_INTERVAL_SECONDS,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError

_PROFILE_DELETION_BUSY_INTERVAL_SECONDS = BUSY_INTERVAL_SECONDS


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
    """Return one reviewed/selected action, a completed removal, or cancellation."""

    state = ProfilePickerState.create(
        build_picker_rows(entries, current=current),
        current=current,
        registry_generation=registry_generation,
        initial_status=initial_status,
        initial_row_index=initial_row_index,
    )
    if apply_removal is not None and not callable(apply_removal):
        raise ValueError("Profile removal handler must be callable.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive profile selection requires a terminal. "
            "Pass a profile name explicitly."
        )

    background_turn: BackgroundExecutorTurn[str] = BackgroundExecutorTurn(
        interval_seconds=_PROFILE_DELETION_BUSY_INTERVAL_SECONDS,
    )
    background_result: ProfilePickerRefresh | None = None
    view = ProfilePickerView(state, background_turn)
    bindings = KeyBindings()
    name_mode = (view.create_mode | view.rename_mode) & Condition(
        lambda: state.edit is not None
        and view.layout.has_focus(view.active_name_field().input)
    )

    def clear_stale_name_error(_buffer) -> None:
        if state.edit is not None:
            state.notify()

    for field in view.name_fields.values():
        field.input.buffer.on_text_changed += clear_stale_name_error

    def focus_stage() -> None:
        # Restoring a reviewed draft is not a user edit. Keep its back-navigation
        # receipt even when setting the buffer invokes the text-change callback.
        message, is_error = state.status, state.status_is_error
        view.focus_stage()
        state.notify(message, error=is_error)

    @bindings.add("down", filter=view.picker_mode)
    def _next_row(event) -> None:
        state.move(1)
        event.app.invalidate()

    @bindings.add("up", filter=view.picker_mode)
    def _previous_row(event) -> None:
        state.move(-1)
        event.app.invalidate()

    @bindings.add("enter", filter=view.picker_mode)
    def _accept_profile(event) -> None:
        action = state.use_profile()
        if action is not None:
            event.app.exit(result=action)
        else:
            event.app.invalidate()

    @bind_case_insensitive_key(bindings, "n", filter=view.picker_mode, eager=True)
    def _edit_new_profile_name(event) -> None:
        state.begin_create()
        focus_stage()
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "r", filter=view.picker_mode, eager=True)
    def _edit_profile_name(event) -> None:
        state.begin_rename()
        focus_stage()
        event.app.invalidate()

    @bindings.add("enter", filter=name_mode, eager=True)
    def _review_name(event) -> None:
        try:
            state.review_name(view.active_name_field().validate_candidate())
        except (ProfileConfigError, TypeError, ValueError) as error:
            state.notify(display_escape_text(str(error)), error=True)
            event.app.invalidate()
            return
        focus_stage()
        event.app.invalidate()

    @bindings.add("c-j", filter=name_mode, eager=True)
    def _reject_name_newline(event) -> None:
        edit = state.edit
        assert edit is not None
        target_kind = "Study" if edit.kind == "RENAME_STUDY" else "Profile"
        state.notify(f"{target_kind} name must stay on one line", error=True)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "d", filter=view.picker_mode, eager=True)
    def _review_removal(event) -> None:
        state.review_removal()
        event.app.invalidate()

    @bind_exact_command_approval(bindings, filter=view.review_mode, eager=True)
    def _apply_reviewed_action(event) -> None:
        nonlocal background_result
        action = state.action
        assert action is not None
        reviewed_row_index = state.index
        # Short registry mutations return frozen receipts; the selector reloads
        # the next generation. Deletion retains its close-after-completion UI.
        if (
            action.kind
            in {
                "CREATE_PROFILE",
                "RENAME_PROFILE",
                "RENAME_STUDY",
            }
            or apply_removal is None
        ):
            event.app.exit(result=action)
            return

        def on_success(message: str) -> None:
            nonlocal background_result
            background_result = ProfilePickerRefresh(
                status=message,
                preferred_row_index=reviewed_row_index,
            )

        def on_error(error: Exception) -> None:
            nonlocal background_result
            background_result = ProfilePickerRefresh(
                status="",
                error=error,
                preferred_row_index=reviewed_row_index,
            )

        def finish(*, close_requested: bool) -> None:
            result = background_result
            if result is None:
                result = ProfilePickerRefresh(
                    status="",
                    error=RuntimeError("Profile deletion finished without a result."),
                )
            event.app.exit(result=replace(result, close_requested=close_requested))

        background_turn.start(
            event.app,
            work=lambda: apply_removal(action),
            on_success=on_success,
            on_error=on_error,
            on_idle=lambda: finish(close_requested=False),
            on_close=lambda: finish(close_requested=True),
        )
        event.app.invalidate()

    def request_close(_event) -> bool:
        if not background_turn.request_close():
            return False
        state.notify("Close requested · deletion will finish first")
        return True

    def back_stage(_event) -> bool:
        if not state.back():
            return False
        focus_stage()
        return True

    @bindings.add("escape")
    def _back_or_cancel(event) -> None:
        dispatch_tui_back(
            event,
            request_close,
            back_stage,
            close=lambda event: event.app.exit(result=None),
        )

    @bind_case_insensitive_key(bindings, "q", filter=view.picker_mode, eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        if request_close(event):
            event.app.invalidate()
        else:
            event.app.exit(result=None)

    app: Application[ProfilePickerAction | ProfilePickerRefresh | None] = Application(
        layout=view.layout,
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=view.style,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
