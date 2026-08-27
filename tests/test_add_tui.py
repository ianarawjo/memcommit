"""Interactive Add draft and terminal-flow contracts."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.application.operations.add.application import AddedMemory, AddRequest, AddResult
from memcommit.adapters.interfaces.tui.operations.add import (
    AddDraftState,
    AddTuiSetup,
    run_add_tui,
)


def _setup(*names: str, selected: str = "target") -> AddTuiSetup:
    return AddTuiSetup(
        names=names or ("target",),
        selectable_names=frozenset(names or ("target",)),
        selected_context=selected,
        current_context=selected,
    )


def _result(request: AddRequest) -> AddResult:
    return AddResult(
        context_name=request.context_locator or "target",
        context_uid="context-uid",
        memories=tuple(
            AddedMemory(uid=f"memory-{index}", content=content)
            for index, content in enumerate(request.contents, start=1)
        ),
        checkpoint_uid="checkpoint-uid",
    )


def test_draft_state_preserves_multiline_text_and_cancelled_new_draft() -> None:
    state = AddDraftState()
    state.begin_edit()
    state.save_edit("First line.\nSecond line.")
    state.new()
    state.cancel_edit()

    assert state.drafts == ["First line.\nSecond line."]
    assert state.ready_contents == ("First line.\nSecond line.",)


def test_draft_state_supports_ordered_create_edit_and_delete() -> None:
    state = AddDraftState()
    state.begin_edit()
    state.save_edit("First")
    state.new()
    state.save_edit("Second")
    state.move(-1)
    state.begin_edit()
    state.save_edit("First revised")
    state.move(1)
    state.delete_selected()

    assert state.ready_contents == ("First revised",)
    assert state.cursor == 0


def test_tui_e_to_edit_adds_multiple_explicit_multiline_drafts() -> None:
    requests: list[AddRequest] = []

    def execute(request: AddRequest) -> AddResult:
        requests.append(request)
        return _result(request)

    with create_pipe_input() as pipe_input:
        # Initial focus is the draft surface. Enter is an editor newline,
        # Ctrl-S saves locally, N starts another draft, and the To Do Enter is
        # the only durable action. A final Enter closes the success receipt.
        pipe_input.send_text("eFirst line.\rSecond line.\x13nAnother.\x13\t\r\r")
        returned = run_add_tui(
            setup=_setup(),
            execute=execute,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == _result(requests[0])
    assert len(requests) == 1
    assert requests[0].contents == (
        "First line.\nSecond line.",
        "Another.",
    )
    assert requests[0].context_locator == "target"
    assert requests[0].source.mode == "TUI_DRAFTS"


def test_tui_context_selector_changes_exact_add_target() -> None:
    requests: list[AddRequest] = []
    with create_pipe_input() as pipe_input:
        # Shift-Tab reaches the shared Context selector, Up selects alpha,
        # Enter stages it, Tab returns to drafts, and the normal draft flow
        # executes against that exact selected Context.
        pipe_input.send_text("\x1b[Z\x1b[A\r\teOnly alpha receives this.\x13\t\r\r")
        returned = run_add_tui(
            setup=_setup("alpha", "target", selected="target"),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert requests[0].context_locator == "alpha"


def test_tui_escape_cancels_without_calling_application() -> None:
    requests: list[AddRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_add_tui(
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []


def test_tui_ctrl_c_cancels_without_calling_application() -> None:
    requests: list[AddRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("eUncommitted draft.\x03")
        returned = run_add_tui(
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []
