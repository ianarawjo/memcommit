"""Interactive Query question, source, scope, and answer contracts."""

import threading

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import typer

import memcommit.commands.query as query_command
import memcommit.commands.query_workbench as query_workbench_module
from memcommit.commands.query_execution import (
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQueryTarget,
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)
from memcommit.commands.query_workbench import (
    QueryAnswerFocus,
    query_answer_stop_count,
    render_query_answer_fragments,
    run_query_workbench,
)
from memcommit.find_answer_references import (
    FindAnswerEvidence,
    FindAnswerSentence,
    build_find_answer_reference_document,
)
from memcommit.query_sessions import AuthorityQueryCatalogEntry


def test_blank_query_workbench_does_not_connect_before_submission():
    ordinary: list[OrdinaryQueryRequest] = []
    granted: list[GrantedQueryRequest] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x03")
        result = run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(),
            run_ordinary=lambda request: ordinary.append(request),  # type: ignore[arg-type,return-value]
            run_granted=lambda request: granted.append(request),  # type: ignore[arg-type,return-value]
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.response is None
    assert ordinary == []
    assert granted == []


def test_query_question_keeps_h_and_uppercase_h_as_text():
    requests: list[OrdinaryQueryRequest] = []

    def ordinary(request: OrdinaryQueryRequest) -> OrdinaryQueryResponse:
        requests.append(request)
        return OrdinaryQueryResponse(request, "Answer.", True)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("hH question\r\x03")
        run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(),
            run_ordinary=ordinary,
            run_granted=lambda _request: (_ for _ in ()).throw(AssertionError()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests[0].question == "hH question"


def test_query_binds_help_only_after_leaving_the_question(monkeypatch):
    help_opened = threading.Event()

    def bind_help(bindings, *, filter, **_kwargs):
        @bindings.add("h", filter=filter, eager=True)
        def open_help(_event) -> None:
            help_opened.set()

    monkeypatch.setattr(query_workbench_module, "bind_session_help", bind_help)

    with create_pipe_input() as pipe_input:
        def drive() -> None:
            pipe_input.send_text("\th")
            if not help_opened.wait(3):
                pipe_input.send_text("\x03")
                return
            pipe_input.send_text("\x03")

        driver = threading.Thread(target=drive, daemon=True)
        driver.start()
        result = run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(),
            run_ordinary=lambda _request: (_ for _ in ()).throw(AssertionError()),
            run_granted=lambda _request: (_ for _ in ()).throw(AssertionError()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        driver.join(timeout=3)

    assert result.status == "CLOSED"
    assert help_opened.is_set()
    assert not driver.is_alive()


def test_escape_closes_the_root_question_without_submission():
    ordinary: list[OrdinaryQueryRequest] = []
    granted: list[GrantedQueryRequest] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(),
            run_ordinary=lambda request: ordinary.append(request),  # type: ignore[arg-type,return-value]
            run_granted=lambda request: granted.append(request),  # type: ignore[arg-type,return-value]
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CLOSED"
    assert result.response is None
    assert ordinary == []
    assert granted == []


def test_query_workbench_asks_visible_contexts_with_exact_visible_scope():
    requests: list[OrdinaryQueryRequest] = []

    def ordinary(request: OrdinaryQueryRequest) -> OrdinaryQueryResponse:
        requests.append(request)
        return OrdinaryQueryResponse(request, "Grounded answer.", True)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("What changed?\r\x03")
        result = run_query_workbench(
            ("task", "task/source", "other"),
            current_context="task",
            initial_context="task",
            query_targets=(),
            run_ordinary=ordinary,
            run_granted=lambda _request: (_ for _ in ()).throw(AssertionError()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        OrdinaryQueryRequest(
            "What changed?",
            ("task", "task/source"),
            include_descendants=False,
            follow_embeds=True,
        )
    ]
    assert result.response == OrdinaryQueryResponse(
        requests[0],
        "Grounded answer.",
        True,
    )


def test_query_answer_focus_moves_by_reference_and_uses_shared_blue_surface():
    request = OrdinaryQueryRequest("What changed?", ("task",))
    document = build_find_answer_reference_document(
        (
            FindAnswerEvidence(
                "m1",
                "task/a",
                "memory",
                "11111111-memory",
                "First supporting Memory.",
            ),
            FindAnswerEvidence(
                "m2",
                "task/b",
                "memory",
                "22222222-memory",
                "Second supporting Memory.",
            ),
        ),
        (
            FindAnswerSentence("First claim.", ("m1",)),
            FindAnswerSentence("Second claim.", ("m2",)),
            FindAnswerSentence("Third claim."),
        ),
    )
    response = OrdinaryQueryResponse(
        request,
        document.text,
        True,
        document,
    )
    focus = QueryAnswerFocus()

    assert query_answer_stop_count(response) == 3
    assert focus.move(response, 1) is True
    first = render_query_answer_fragments(response, focus=focus, focused=True)
    assert ("[SetCursorPosition]", "") in first
    assert any(
        style == "class:memcommit.choice.active.focused"
        and text.startswith("[1] m1 · memory")
        for style, text in first
    )
    assert any(
        style == "" and text.startswith("[2] m2 · memory")
        for style, text in first
    )

    assert focus.move(response, 1) is True
    assert focus.move(response, 1) is False
    second_unfocused = render_query_answer_fragments(
        response,
        focus=focus,
        focused=False,
    )
    assert any(
        style == "class:memcommit.choice.active"
        and text.startswith("[2] m2 · memory")
        for style, text in second_unfocused
    )
    assert ("[SetCursorPosition]", "") not in second_unfocused

    focus.enter(response, 1)
    assert focus.stop_index == 0
    focus.enter(response, -1)
    assert focus.stop_index == 2


def test_query_workbench_switches_to_a_typed_query_only_view():
    target = GrantedQueryTarget(
        grant_uid="grant-one",
        public_name="campus-wiki/construction-details",
        attachment_name="task",
        session_log_allowed=True,
    )
    requests: list[GrantedQueryRequest] = []

    def granted(request: GrantedQueryRequest) -> GrantedQueryResponse:
        requests.append(request)
        return GrantedQueryResponse(request, answer="Authorized answer.")

    with create_pipe_input() as pipe_input:
        # Question -> Sources -> Scope; change SOURCE TYPE, return to Question,
        # submit, then request close after the frozen turn.
        pipe_input.send_text("What is required?\t\t\x1b[C/\r\x03")
        run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(target,),
            run_ordinary=lambda _request: (_ for _ in ()).throw(AssertionError()),
            run_granted=granted,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        GrantedQueryRequest(
            target=target,
            question="What is required?",
            federate_descendants=True,
        )
    ]


def test_query_only_view_can_browse_opaque_catalog_without_a_question():
    target = GrantedQueryTarget(
        grant_uid="grant-one",
        public_name="construction-details",
        attachment_name="task",
        session_log_allowed=False,
    )
    requests: list[GrantedQueryRequest] = []

    def granted(request: GrantedQueryRequest) -> GrantedQueryResponse:
        requests.append(request)
        return GrantedQueryResponse(
            request,
            catalog=(
                AuthorityQueryCatalogEntry(
                    handle="q-123456789abc",
                    placeholder_lines=("Flow Circular",),
                ),
            ),
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\x1b[C/\r\x03")
        result = run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(target,),
            run_ordinary=lambda _request: (_ for _ in ()).throw(AssertionError()),
            run_granted=granted,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [GrantedQueryRequest(target=target, question=None)]
    assert isinstance(result.response, GrantedQueryResponse)
    assert result.response.catalog[0].handle == "q-123456789abc"


def test_typed_granted_query_response_rejects_mixed_answer_and_catalog():
    target = GrantedQueryTarget(
        grant_uid="grant-one",
        public_name="construction-details",
        attachment_name="task",
        session_log_allowed=False,
    )
    request = GrantedQueryRequest(target=target, question="What changed?")

    with pytest.raises(ValueError, match="cannot also expose a catalog"):
        GrantedQueryResponse(
            request,
            answer="Grounded answer.",
            catalog=(
                AuthorityQueryCatalogEntry(
                    handle="q-123456789abc",
                    placeholder_lines=("Flow Circular",),
                ),
            ),
        )


def test_query_workbench_saves_only_an_explicit_query_view_session():
    target = GrantedQueryTarget(
        grant_uid="grant-one",
        public_name="construction-details",
        attachment_name="task",
        session_log_allowed=True,
    )
    requests: list[GrantedQueryRequest] = []

    def granted(request: GrantedQueryRequest) -> GrantedQueryResponse:
        requests.append(request)
        return GrantedQueryResponse(request, answer="Saved answer.")

    with create_pipe_input() as pipe_input:
        # Select query-only mode, move to SESSION LOG, turn it on, enter the
        # newly visible exact session name, return to Question, and submit.
        pipe_input.send_text(
            "Question?\t\t\x1b[C\x1b[B\x1b[B\x1b[C\t"
            "review-log\r\r\x03"
        )
        run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(target,),
            run_ordinary=lambda _request: (_ for _ in ()).throw(AssertionError()),
            run_granted=granted,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        GrantedQueryRequest(
            target=target,
            question="Question?",
            session_name="review-log",
            federate_descendants=False,
        )
    ]


def test_initial_saved_session_is_visibly_and_executably_exact():
    target = GrantedQueryTarget(
        grant_uid="grant-one",
        public_name="construction-details",
        attachment_name="task",
        session_log_allowed=True,
    )
    requests: list[GrantedQueryRequest] = []

    def granted(request: GrantedQueryRequest) -> GrantedQueryResponse:
        requests.append(request)
        return GrantedQueryResponse(request, answer="Saved answer.")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Question?\r\x03")
        run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(target,),
            run_ordinary=lambda _request: (_ for _ in ()).throw(AssertionError()),
            run_granted=granted,
            initial_session_name="review-log",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        GrantedQueryRequest(
            target=target,
            question="Question?",
            session_name="review-log",
            federate_descendants=False,
        )
    ]


def test_bare_query_routes_to_the_workbench_only_in_a_terminal(
    isolated_store,
    monkeypatch,
):
    observed: list[tuple[object, ...]] = []
    monkeypatch.setattr(query_command, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        query_command,
        "_open_query_workbench",
        lambda store, **kwargs: observed.append((store.store_dir, kwargs)),
    )

    query_command.cmd(
        selector=None,
        question=None,
        context_name=None,
        language="en",
        session_name=None,
        sessions=False,
        show_session_name=None,
    )

    assert observed == [
        (
            query_command.MemoryStore().store_dir,
            {"context_name": None, "language": "en", "session_name": None},
        )
    ]


def test_bare_query_outside_a_terminal_keeps_an_explicit_input_error(
    isolated_store,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(query_command, "_interactive_terminal", lambda: False)

    with pytest.raises(typer.Exit):
        query_command.cmd(
            selector=None,
            question=None,
            context_name=None,
            language="en",
            session_name=None,
            sessions=False,
            show_session_name=None,
        )

    assert "SELECTOR is required outside a terminal" in capsys.readouterr().err
