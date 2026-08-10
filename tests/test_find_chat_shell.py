from __future__ import annotations

import threading
import time
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
        content=("Dining will not operate during construction. Main building cafe."),
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
    assert snapshot.index("SEARCH RESULTS") < snapshot.index("YOU")
    assert snapshot.index("YOU") < snapshot.index("I found five")
    assert "interactive input not shown" in snapshot


def test_snapshot_separates_related_fallback_from_primary_matches():
    related = FindChatResult(
        alias="m1",
        context_name="task-3/personal-memory/2024/03",
        kind="memory",
        uid="9c9a8333",
        content="The instructions describe an evening medication time.",
        relevance="related",
    )
    state = FindChatState(
        context_name="task-3",
        current_query="health insurance memories",
        results=(related,),
        related_query="health and healthcare memories",
        status="NO PRIMARY MATCHES · SHOWING RELATED RESULTS",
    )

    snapshot = render_find_chat_snapshot(state)

    assert "PRIMARY MATCHES 0 · RELATED 1 · KEPT 0" in snapshot
    assert "PRIMARY MATCHES\n  (none)" in snapshot
    assert "RELATED RESULTS" in snapshot
    assert "Broader search: health and healthcare memories" in snapshot
    assert "Related items do not satisfy the original query." in snapshot
    assert "[m1 related memory" in snapshot


def test_related_results_require_one_query_and_cannot_mix_with_primary():
    related = FindChatResult(
        alias="m2",
        context_name="task-3",
        kind="memory",
        uid="related-one",
        content="Related content",
        relevance="related",
    )
    with pytest.raises(ValueError, match="require one related query"):
        FindChatState(context_name="task-3", results=(related,))

    with pytest.raises(ValueError, match="cannot mix"):
        FindChatState(
            context_name="task-3",
            results=(TASK_1_CAFE_RESULTS[0], related),
            related_query="broader topic",
        )


def test_interactive_view_opens_at_the_first_ranked_result():
    content = FormattedTextControl(_result_text(_state())).create_content(
        width=80, height=12
    )
    first_line = "".join(text for _style, text in content.get_line(0))

    assert first_line == "SEARCH RESULTS"
    assert "38b46e04" in "".join(
        text
        for line_number in range(content.line_count)
        for _style, text in content.get_line(line_number)
    )


def test_result_arrow_keys_move_the_read_only_scroll_cursor(monkeypatch):
    original_text_area = find_chat_shell_module.TextArea
    original_build_tui_frame = find_chat_shell_module.build_tui_frame
    captured = {}

    def capturing_text_area(*args, **kwargs):
        text_area = original_text_area(*args, **kwargs)
        if kwargs.get("read_only") is True:
            key = (
                "results"
                if kwargs.get("text", "").startswith("SEARCH RESULTS")
                else "dialogue"
            )
            captured[key] = text_area
        return text_area

    monkeypatch.setattr(
        find_chat_shell_module,
        "TextArea",
        capturing_text_area,
    )

    def capturing_frame(*regions):
        captured["regions"] = regions
        return original_build_tui_frame(*regions)

    monkeypatch.setattr(
        find_chat_shell_module,
        "build_tui_frame",
        capturing_frame,
    )
    with create_pipe_input() as pipe_input:
        # Input → results, then move down and close from results.
        pipe_input.send_text("\t\x1b[Bq")
        action = run_find_chat_shell(
            _state(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    results_area = captured["results"]
    assert action == FindChatAction(kind="CLOSE")
    assert captured["regions"][1].container is results_area.window
    assert results_area.buffer.document.cursor_position_row == 1
    assert results_area.buffer.read_only()


def test_escape_closes_find_chat_from_the_root_input():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        action = run_find_chat_shell(
            _state(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action == FindChatAction(kind="CLOSE")


def test_dialogue_arrow_keys_scroll_long_references(monkeypatch):
    original_text_area = find_chat_shell_module.TextArea
    captured = {}

    def capturing_text_area(*args, **kwargs):
        text_area = original_text_area(*args, **kwargs)
        text = kwargs.get("text", "")
        if kwargs.get("read_only") is True and not text.startswith("SEARCH RESULTS"):
            captured["dialogue"] = text_area
        return text_area

    monkeypatch.setattr(
        find_chat_shell_module,
        "TextArea",
        capturing_text_area,
    )
    state = _state(
        messages=(
            FindChatMessage(
                role="MEM",
                text="\n".join(f"Reference line {index}" for index in range(20)),
            ),
        )
    )
    with create_pipe_input() as pipe_input:
        # Input → results → dialogue, move one logical line up, then close.
        pipe_input.send_text("\t\t\x1b[Aq")
        action = run_find_chat_shell(
            state,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    dialogue_area = captured["dialogue"]
    assert action == FindChatAction(kind="CLOSE")
    assert dialogue_area.buffer.document.cursor_position_row == 19
    assert dialogue_area.buffer.read_only()


def test_empty_state_starts_with_an_open_find_question():
    snapshot = render_find_chat_snapshot(FindChatState(context_name="task-1"))

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


def test_session_keeps_one_application_for_repeated_controller_turns(
    monkeypatch,
):
    original_application = find_chat_shell_module.Application
    original_header = find_chat_shell_module.render_find_chat_header
    application_count = 0
    first_applied = threading.Event()
    second_applied = threading.Event()
    feeder_errors = []

    def capturing_application(*args, **kwargs):
        nonlocal application_count
        application_count += 1
        return original_application(*args, **kwargs)

    def capturing_header(state):
        if state.status == "TURN 1 READY":
            first_applied.set()
        elif state.status == "TURN 2 READY":
            second_applied.set()
        return original_header(state)

    monkeypatch.setattr(
        find_chat_shell_module,
        "Application",
        capturing_application,
    )
    monkeypatch.setattr(
        find_chat_shell_module,
        "render_find_chat_header",
        capturing_header,
    )
    calls = []

    def handle_turn(state: FindChatState, text: str) -> FindChatState:
        calls.append(text)
        narrowed = tuple(
            result
            for result in state.results
            if "coffee machine" in result.content.casefold()
        )
        return replace(
            state,
            current_query=f"turn {len(calls)}",
            messages=(
                *state.messages,
                FindChatMessage(role="USER", text=text),
                FindChatMessage(
                    role="MEM",
                    text=f"Completed turn {len(calls)}.",
                ),
            ),
            results=narrowed,
            kept_count=0,
            status=f"TURN {len(calls)} READY",
        )

    with create_pipe_input() as pipe_input:

        def feed_turns() -> None:
            try:
                pipe_input.send_text("first refinement\r")
                if not first_applied.wait(2):
                    raise AssertionError("first turn was not rendered")
                pipe_input.send_text("second refinement\r")
                if not second_applied.wait(2):
                    raise AssertionError("second turn was not rendered")
                pipe_input.send_text("\x03")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)

        feeder = threading.Thread(target=feed_turns)
        feeder.start()
        result = run_find_chat_session(
            _state(kept_count=0),
            handle_turn=handle_turn,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert application_count == 1
    assert result == FindChatSessionResult(
        status="CLOSED",
        state=result.state,
        submitted_turns=("first refinement", "second refinement"),
    )
    assert calls == ["first refinement", "second refinement"]
    assert result.state.current_query == "turn 2"
    assert [item.uid for item in result.state.results] == ["cad72ae2"]
    assert result.state.status == "TURN 2 READY"
    assert result.state.messages[-1].text == "Completed turn 2."


def test_failed_controller_turn_preserves_results_in_same_application():
    def fail(_state: FindChatState, _text: str) -> FindChatState:
        raise RuntimeError("provider unavailable")

    initial = _state()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("try another search\r\x03")
        result = run_find_chat_session(
            initial,
            handle_turn=fail,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.state.results == initial.results
    assert result.state.status == "TURN FAILED · RESULTS UNCHANGED"
    assert result.state.messages[-1].role == "STATUS"
    assert "provider unavailable" in result.state.messages[-1].text


def test_busy_indicator_cycles_dot_frames_until_the_turn_finishes(monkeypatch):
    original_label = find_chat_shell_module._processing_find_turn_label
    rendered_frames: set[str] = set()
    all_frames_rendered = threading.Event()
    handler_started = threading.Event()
    release_handler = threading.Event()
    feeder_errors = []

    def capture_label(frame_index: int) -> str:
        label = original_label(frame_index)
        rendered_frames.add(label)
        if len(rendered_frames) == 3:
            all_frames_rendered.set()
        return label

    monkeypatch.setattr(
        find_chat_shell_module,
        "_processing_find_turn_label",
        capture_label,
    )
    monkeypatch.setattr(
        find_chat_shell_module,
        "_FIND_BUSY_INTERVAL_SECONDS",
        0.01,
    )

    def handle_turn(state: FindChatState, _text: str) -> FindChatState:
        handler_started.set()
        if not release_handler.wait(2):
            raise RuntimeError("test did not release handler")
        return replace(state, status="REFINED")

    with create_pipe_input() as pipe_input:

        def close_after_animation() -> None:
            try:
                pipe_input.send_text("healthcare\r")
                if not handler_started.wait(2):
                    raise AssertionError("handler did not start")
                if not all_frames_rendered.wait(2):
                    raise AssertionError("busy indicator did not animate")
                pipe_input.send_text("\x03")
                release_handler.set()
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
                release_handler.set()

        feeder = threading.Thread(target=close_after_animation)
        feeder.start()
        result = run_find_chat_session(
            _state(),
            handle_turn=handle_turn,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert rendered_frames == {
        " PROCESSING FIND TURN .",
        " PROCESSING FIND TURN ..",
        " PROCESSING FIND TURN …",
    }
    assert result.state.status == "REFINED"


def test_busy_turn_stays_visible_and_blocks_parallel_submission(monkeypatch):
    original_header = find_chat_shell_module.render_find_chat_header
    thinking_rendered = threading.Event()
    handler_started = threading.Event()
    release_handler = threading.Event()
    feeder_errors = []
    calls = []

    def capturing_header(state):
        if state.status == "THINKING · RESULTS UNCHANGED":
            thinking_rendered.set()
        return original_header(state)

    monkeypatch.setattr(
        find_chat_shell_module,
        "render_find_chat_header",
        capturing_header,
    )

    def handle_turn(state: FindChatState, text: str) -> FindChatState:
        calls.append(text)
        handler_started.set()
        if not release_handler.wait(2):
            raise RuntimeError("test did not release handler")
        return replace(
            state,
            messages=(
                *state.messages,
                FindChatMessage(role="USER", text=text),
                FindChatMessage(role="MEM", text="Finished."),
            ),
            status="ANSWER READY",
        )

    with create_pipe_input() as pipe_input:

        def feed_while_busy() -> None:
            try:
                pipe_input.send_text("first turn\r")
                if not handler_started.wait(2):
                    raise AssertionError("handler did not start")
                if not thinking_rendered.wait(2):
                    raise AssertionError("thinking state was not rendered")
                pipe_input.send_text("parallel turn\r")
                pipe_input.send_text("\x03")
                release_handler.set()
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
                release_handler.set()

        feeder = threading.Thread(target=feed_while_busy)
        feeder.start()
        result = run_find_chat_session(
            _state(),
            handle_turn=handle_turn,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert calls == ["first turn"]
    assert result.submitted_turns == ("first turn",)
    assert result.state.status == "ANSWER READY"


def test_busy_control_d_waits_for_the_current_turn():
    handler_started = threading.Event()
    release_handler = threading.Event()

    def handle_turn(state: FindChatState, text: str) -> FindChatState:
        handler_started.set()
        if not release_handler.wait(2):
            raise RuntimeError("test did not release handler")
        return replace(
            state,
            messages=(
                *state.messages,
                FindChatMessage(role="USER", text=text),
                FindChatMessage(role="MEM", text="Finished before EOF close."),
            ),
            status="ANSWER READY",
        )

    with create_pipe_input() as pipe_input:

        def close_while_busy() -> None:
            pipe_input.send_text("first turn\r")
            assert handler_started.wait(2)
            pipe_input.send_text("\x04")
            release_handler.set()

        feeder = threading.Thread(target=close_while_busy)
        feeder.start()
        result = run_find_chat_session(
            _state(),
            handle_turn=handle_turn,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert not feeder.is_alive()
    assert result.submitted_turns == ("first turn",)
    assert result.state.status == "ANSWER READY"


def test_input_stream_eof_during_busy_turn_preserves_completed_state():
    handler_started = threading.Event()
    release_handler = threading.Event()

    def handle_turn(state: FindChatState, text: str) -> FindChatState:
        handler_started.set()
        if not release_handler.wait(2):
            raise RuntimeError("test did not release handler")
        return replace(
            state,
            messages=(
                *state.messages,
                FindChatMessage(role="USER", text=text),
                FindChatMessage(role="MEM", text="Finished after stream EOF."),
            ),
            status="ANSWER READY",
        )

    with create_pipe_input() as pipe_input:

        def end_input_while_busy() -> None:
            pipe_input.send_text("first turn\r")
            assert handler_started.wait(2)
            pipe_input.close()
            # Give prompt-toolkit's input callback time to begin teardown
            # before the non-cancellable executor worker returns.
            time.sleep(0.05)
            release_handler.set()

        feeder = threading.Thread(target=end_input_while_busy)
        feeder.start()
        result = run_find_chat_session(
            _state(),
            handle_turn=handle_turn,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert not feeder.is_alive()
    assert result.submitted_turns == ("first turn",)
    assert result.state.status == "ANSWER READY"
    assert result.state.messages[-1].text == "Finished after stream EOF."


@pytest.mark.parametrize("keys", ["\x03", "\x04", "\tq", "\t\tq"])
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
