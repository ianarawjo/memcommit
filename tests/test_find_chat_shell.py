from __future__ import annotations

from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.layout import FormattedTextControl
from prompt_toolkit.output import DummyOutput

import memcommit.commands.find_chat_shell as find_chat_shell_module
from memcommit.commands.find_chat_shell import (
    FindChatAction,
    FindChatMessage,
    FindChatResult,
    FindChatSessionResult,
    FindChatState,
    _result_text,
    render_find_chat_snapshot,
    run_find_chat_session,
    run_find_chat_shell,
)


TASK_1_CAFE_RESULTS = (
    FindChatResult(
        alias="m1",
        context_name="temp/task-1-atomized-en",
        kind="memory",
        uid="38b46e04",
        content=(
            "The first-floor campus store will close. The one in the "
            "engineering building will remain open, so people must be "
            "directed there instead. During this period, the engineering "
            "building store will have extended hours, from 7 to 11, to "
            "match the hours of the first-floor campus store."
        ),
    ),
    FindChatResult(
        alias="m2",
        context_name="temp/task-1-atomized-en",
        kind="memory",
        uid="6a53b8ae",
        content=(
            "Dining will not operate during construction. "
            "Main building cafe."
        ),
    ),
    FindChatResult(
        alias="m3",
        context_name="temp/task-1-atomized-en",
        kind="memory",
        uid="cad72ae2",
        content=(
            "There is no coffee, well, the cafe is closed, but there is a "
            "coffee machine on the first floor, so please use that."
        ),
    ),
    FindChatResult(
        alias="m4",
        context_name="temp/task-1-atomized-en",
        kind="memory",
        uid="bb377c00",
        content=(
            "Students usually come in the evening because of the ATM and "
            "24-hour store; they are temporarily closed, so ask the students "
            "to go to an appropriate place."
        ),
    ),
    FindChatResult(
        alias="m5",
        context_name="temp/task-1-atomized-en",
        kind="memory",
        uid="9a336349",
        content=(
            "There are no alternative facilities. Use other places on or "
            "off campus. During summer break, the only place for regular "
            "meals was the engineering building."
        ),
    ),
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
        "results": TASK_1_CAFE_RESULTS,
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
    assert snapshot.count("temp/task-1-atomized-en") == 2
    assert "[m1 memory  38b46e04] The first-floor campus store" in snapshot
    assert "[m2 memory  6a53b8ae] Dining will not operate" in snapshot
    assert "[m3 memory  cad72ae2] There is no coffee" in snapshot
    assert "[m4 memory  bb377c00] Students usually come" in snapshot
    assert "[m5 memory  9a336349] There are no alternative" in snapshot
    assert snapshot.index("38b46e04") < snapshot.index("6a53b8ae")
    assert snapshot.index("6a53b8ae") < snapshot.index("cad72ae2")
    assert snapshot.index("cad72ae2") < snapshot.index("bb377c00")
    assert snapshot.index("bb377c00") < snapshot.index("9a336349")
    assert "interactive input not shown" in snapshot


def test_interactive_view_opens_at_the_first_ranked_result():
    content = FormattedTextControl(
        _result_text(_state())
    ).create_content(width=80, height=12)
    first_line = "".join(
        text for _style, text in content.get_line(0)
    )

    assert first_line == "SEARCH RESULTS"
    assert "38b46e04" in "".join(
        text
        for line_number in range(content.line_count)
        for _style, text in content.get_line(line_number)
    )


def test_result_arrow_keys_move_the_read_only_scroll_cursor(monkeypatch):
    original_text_area = find_chat_shell_module.TextArea
    captured = {}

    def capturing_text_area(*args, **kwargs):
        text_area = original_text_area(*args, **kwargs)
        if kwargs.get("read_only"):
            captured["results"] = text_area
        return text_area

    monkeypatch.setattr(
        find_chat_shell_module,
        "TextArea",
        capturing_text_area,
    )
    with create_pipe_input() as pipe_input:
        # Input → dialogue → results, then move down and close from results.
        pipe_input.send_text("\t\t\x1b[Bq")
        action = run_find_chat_shell(
            _state(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    results_area = captured["results"]
    assert action == FindChatAction(kind="CLOSE")
    assert results_area.buffer.document.cursor_position_row == 1
    assert results_area.buffer.read_only()


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


def test_session_reopens_with_controller_refined_results(monkeypatch):
    actions = iter(
        [
            FindChatAction(
                kind="SUBMIT",
                text="only the first-floor coffee-machine result",
            ),
            FindChatAction(kind="CLOSE"),
        ]
    )
    monkeypatch.setattr(
        find_chat_shell_module,
        "run_find_chat_shell",
        lambda *_args, **_kwargs: next(actions),
    )

    def handle_turn(state: FindChatState, text: str) -> FindChatState:
        narrowed = tuple(
            result
            for result in state.results
            if "coffee machine" in result.content.casefold()
        )
        return replace(
            state,
            current_query=text,
            messages=(
                *state.messages,
                FindChatMessage(role="USER", text=text),
                FindChatMessage(
                    role="MEM",
                    text="I narrowed the current results to one Memory.",
                ),
            ),
            results=narrowed,
            kept_count=0,
            status="REFINED RESULTS READY",
        )

    result = run_find_chat_session(
        _state(kept_count=0),
        handle_turn=handle_turn,
        require_tty=False,
    )

    assert result == FindChatSessionResult(
        status="CLOSED",
        state=result.state,
        submitted_turns=("only the first-floor coffee-machine result",),
    )
    assert result.state.current_query == (
        "only the first-floor coffee-machine result"
    )
    assert [item.uid for item in result.state.results] == ["cad72ae2"]
    assert result.state.status == "REFINED RESULTS READY"
    assert "narrowed" in result.state.messages[-1].text


def test_failed_controller_turn_preserves_results_and_reopens(monkeypatch):
    actions = iter(
        [
            FindChatAction(kind="SUBMIT", text="try another search"),
            FindChatAction(kind="CLOSE"),
        ]
    )
    monkeypatch.setattr(
        find_chat_shell_module,
        "run_find_chat_shell",
        lambda *_args, **_kwargs: next(actions),
    )

    def fail(_state: FindChatState, _text: str) -> FindChatState:
        raise RuntimeError("provider unavailable")

    initial = _state()
    result = run_find_chat_session(
        initial,
        handle_turn=fail,
        require_tty=False,
    )

    assert result.state.results == initial.results
    assert result.state.status == "TURN FAILED · RESULTS UNCHANGED"
    assert result.state.messages[-1].role == "STATUS"
    assert "provider unavailable" in result.state.messages[-1].text


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
