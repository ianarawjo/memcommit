"""Compact one-shot Query Scope, Question, and Answer contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import typer

import memcommit.adapters.console.commands.query.command as query_command
from memcommit.application.operations.search.answer_references import (
    FindAnswerEvidence,
    FindAnswerSentence,
    build_find_answer_reference_document,
)
from memcommit.adapters.interfaces.tui.operations.query import (
    QueryAnswerFocus,
    project_query_answer_clipboard,
    query_answer_stop_count,
    render_query_answer_fragments,
    run_query_workbench,
)
from memcommit.application.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQueryTarget,
)
from memcommit.application.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)


def _unexpected(_request):
    raise AssertionError("unexpected Query route")


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


def test_query_scope_uses_transient_browse_without_todo_or_transcripts():
    source = (
        Path(__file__).parents[1]
        / "src/memcommit/adapters/interfaces/tui/operations/query/screen.py"
    ).read_text(encoding="utf-8")
    assert "CompactReadableScopeControl" in source
    assert "SAVED TRANSCRIPTS" not in source
    assert "TO DO" not in source

    with create_pipe_input() as pipe_input:
        # Question -> Answer -> Source type -> Context input -> Browse; open,
        # close the transient tree, return to Question, then close.
        pipe_input.send_text("\t\t\t\t\r\x1b\x1b\x1b")
        result = run_query_workbench(
            ("task", "task/source", "other"),
            current_context="task",
            initial_context="task",
            query_targets=(),
            run_ordinary=_unexpected,
            run_granted=_unexpected,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CLOSED"
    assert result.response is None


def test_query_question_keeps_shortcut_letters_as_text():
    requests: list[OrdinaryQueryRequest] = []

    def ordinary(request: OrdinaryQueryRequest) -> OrdinaryQueryResponse:
        requests.append(request)
        return OrdinaryQueryResponse(request, "Answer.", True)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("hHyY question\r\x03")
        run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(),
            run_ordinary=ordinary,
            run_granted=_unexpected,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests[0].question == "hHyY question"


def test_query_workbench_freezes_compact_visible_scope_on_enter():
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
            run_granted=_unexpected,
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


def test_query_workbench_switches_to_typed_query_view_scope():
    target = GrantedQueryTarget(
        grant_uid="grant-one",
        public_name="campus-wiki/construction-details",
        attachment_name="task",
    )
    requests: list[GrantedQueryRequest] = []

    def granted(request: GrantedQueryRequest) -> GrantedQueryResponse:
        requests.append(request)
        return GrantedQueryResponse(request, answer="Authorized answer.")

    with create_pipe_input() as pipe_input:
        # Question -> Answer -> Source type, choose Query View, jump back to
        # Question and submit one independent turn.
        pipe_input.send_text("What is required?\t\t\x1b[C/\r\x03")
        run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(target,),
            run_ordinary=_unexpected,
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


def test_query_view_rejects_blank_question_without_running():
    target = GrantedQueryTarget(
        grant_uid="grant-one",
        public_name="construction-details",
        attachment_name="task",
    )
    requests: list[GrantedQueryRequest] = []

    def granted(request: GrantedQueryRequest) -> GrantedQueryResponse:
        requests.append(request)
        return GrantedQueryResponse(request, "Unexpected answer.")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\x1b[C/\r\x03")
        result = run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(target,),
            run_ordinary=_unexpected,
            run_granted=granted,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == []
    assert result.response is None


def test_typed_granted_contract_requires_question_and_answer():
    target = GrantedQueryTarget("grant-one", "construction-details", "task")

    with pytest.raises(ValueError, match="nonblank Query question"):
        GrantedQueryRequest(target=target, question="")
    request = GrantedQueryRequest(target=target, question="What changed?")
    with pytest.raises(ValueError, match="empty answer"):
        GrantedQueryResponse(request, answer="")


def test_query_workbench_can_start_on_one_typed_query_view():
    target = GrantedQueryTarget("grant-one", "construction-details", "task")
    requests: list[GrantedQueryRequest] = []

    def granted(request: GrantedQueryRequest) -> GrantedQueryResponse:
        requests.append(request)
        return GrantedQueryResponse(request, "Authorized answer.")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("What changed?\r\x03")
        run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(target,),
            run_ordinary=_unexpected,
            run_granted=granted,
            initial_query_target=target,
            initial_federate_descendants=False,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert requests == [
        GrantedQueryRequest(
            target=target,
            question="What changed?",
            federate_descendants=False,
        )
    ]


def test_query_answer_focus_and_clipboard_preserve_typed_references():
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
    response = OrdinaryQueryResponse(request, document.text, True, document)
    focus = QueryAnswerFocus()

    assert query_answer_stop_count(response) == 3
    assert focus.move(response, 1) is True
    fragments = render_query_answer_fragments(response, focus=focus, focused=True)
    assert any(
        style == "class:memcommit.choice.active.focused"
        and text.startswith("[1] First supporting Memory.")
        for style, text in fragments
    )
    focused = project_query_answer_clipboard(response, focus=focus)
    assert focused.label == "Reference 1"
    assert focused.text.startswith("[1] First supporting Memory.")
    complete = project_query_answer_clipboard(
        response,
        focus=focus,
        whole_document=True,
    )
    assert complete.text == document.text


def test_bare_query_routes_to_workbench_only_in_a_terminal(
    isolated_store,
    monkeypatch,
):
    observed: list[tuple[object, ...]] = []
    monkeypatch.setattr(query_command, "is_interactive_terminal", lambda: True)
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
    )

    assert observed == [
        (
            query_command.MemoryStore().store_dir,
            {"context_name": None, "language": "en"},
        )
    ]


def test_bare_query_outside_terminal_keeps_explicit_input_error(
    isolated_store,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(query_command, "is_interactive_terminal", lambda: False)

    with pytest.raises(typer.Exit):
        query_command.cmd(
            selector=None,
            question=None,
            context_name=None,
            language="en",
        )

    assert "SELECTOR is required outside a terminal" in capsys.readouterr().err
