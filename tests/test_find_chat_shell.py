from __future__ import annotations

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.find_chat_shell import (
    FindChatAction,
    FindChatMessage,
    FindChatState,
    render_find_chat_snapshot,
    run_find_chat_shell,
)


def _state(**changes) -> FindChatState:
    values = {
        "context_name": "temp/task-1-atomized-en",
        "current_query": "related to cafe and store",
        "messages": (
            FindChatMessage(
                role="USER",
                text="Find things related to the cafe and store.",
            ),
            FindChatMessage(
                role="MEM",
                text="I found five matching Memories.",
            ),
        ),
        "result_count": 5,
        "kept_count": 2,
        "status": "RESULTS READY",
    }
    values.update(changes)
    return FindChatState(**values)


def test_snapshot_exposes_chat_state_without_searching_or_mutating():
    snapshot = render_find_chat_snapshot(_state())

    assert "MEM FIND · INTERACTIVE · temp/task-1-atomized-en" in snapshot
    assert "QUERY · related to cafe and store" in snapshot
    assert "RESULTS 5 · KEPT 2" in snapshot
    assert "YOU" in snapshot
    assert "I found five matching Memories." in snapshot
    assert "interactive input not shown" in snapshot


def test_empty_state_starts_with_an_open_find_question():
    snapshot = render_find_chat_snapshot(
        FindChatState(context_name="task-1")
    )

    assert "QUERY · (not asked yet)" in snapshot
    assert "OPEN QUESTION · FIND" in snapshot
    assert "What are you trying to locate" in snapshot


def test_terminal_controls_are_sanitized_in_controller_supplied_text():
    snapshot = render_find_chat_snapshot(
        _state(
            messages=(
                FindChatMessage(
                    role="MEM",
                    text="safe\x1b[2Jstill visible",
                ),
            )
        )
    )

    assert "\x1b" not in snapshot
    assert "safe�[2Jstill visible" in snapshot


def test_shell_returns_one_submission_for_a_future_controller():
    state = _state()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("only the coffee-machine results\r")
        action = run_find_chat_shell(
            state,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action == FindChatAction(
        kind="SUBMIT",
        text="only the coffee-machine results",
    )
    assert state == _state()


def test_ctrl_j_adds_a_newline_without_submitting_early():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("cafe\nand campus store\r")
        action = run_find_chat_shell(
            _state(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action == FindChatAction(
        kind="SUBMIT",
        text="cafe\nand campus store",
    )


def test_blank_submission_waits_for_a_real_turn():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\rcoffee machine\r")
        action = run_find_chat_shell(
            _state(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.text == "coffee machine"


@pytest.mark.parametrize("keys", ["\x03", "\tq"])
def test_close_returns_without_controller_or_provider_work(keys: str):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        action = run_find_chat_shell(
            _state(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action == FindChatAction(kind="CLOSE")


def test_state_copies_message_sequences_before_waiting():
    messages = [
        FindChatMessage(role="USER", text="first query"),
    ]
    state = FindChatState(context_name="task-1", messages=messages)

    messages.append(FindChatMessage(role="MEM", text="late mutation"))

    assert len(state.messages) == 1


def test_non_tty_entry_has_a_clear_error():
    with pytest.raises(ValueError, match="requires a TTY"):
        run_find_chat_shell(_state(), require_tty=True)
