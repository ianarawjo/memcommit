"""Typed projection and interaction contracts for the Summarize TUI."""

from __future__ import annotations

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.interfaces.tui.operations.summarize import (
    SummarizeTuiOutcome,
    SummarizeTuiSetup,
    project_summarize_clipboard,
    project_summarize_outcome,
    project_summarize_result,
    run_summarize_tui,
)
from memcommit.summarize_application import SummarizeRequest, SummarizeResult
from memcommit.understanding import UnderstandingSummary


def _result() -> SummarizeResult:
    return SummarizeResult(
        context_name="summary/context",
        include_descendants=True,
        follow_embeds=True,
        source_digest="a" * 64,
        source_count=3,
        understanding=UnderstandingSummary(
            text="The Context records one closure and its staff exception.",
            source_uids=("m1", "m2", "m3"),
        ),
    )


def test_summarize_projects_typed_result_without_parsing_plain_output() -> None:
    document = project_summarize_result(_result())

    assert [section.uid for section in document.sections] == [
        "SUMMARY:TITLE",
        "SUMMARY:STATUS",
        "SUMMARY:UNDERSTANDING",
    ]
    rendered = "".join(text for _style, text in document.render(focused_uid=None))
    assert "SUMMARY · summary/context" in rendered
    assert "STATUS · RECURSIVE · SOURCES 3" in rendered
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert "closure and its staff exception" in rendered


def _setup(*names: str, selected: str = "summary/context") -> SummarizeTuiSetup:
    return SummarizeTuiSetup(
        names=names or ("summary/context",),
        selected_context=selected,
        current_context=selected,
    )


def _setup_with_range(
    *names: str,
    selected: str = "summary/context",
    initial_range_mode: str,
) -> SummarizeTuiSetup:
    return SummarizeTuiSetup(
        names=names or ("summary/context",),
        selected_context=selected,
        initial_range_mode=initial_range_mode,
        current_context=selected,
    )


def _result_for_request(
    request: SummarizeRequest,
    *,
    context_name: str = "summary/context",
) -> SummarizeResult:
    return SummarizeResult(
        context_name=context_name,
        include_descendants=request.include_descendants,
        follow_embeds=request.follow_embeds,
        source_digest=("b" if request.include_descendants else "a") * 64,
        source_count=3 if request.include_descendants else 1,
        understanding=_result().understanding,
    )


def test_summarize_tui_executes_only_after_explicit_action_then_closes() -> None:
    requests: list[SummarizeRequest] = []

    def execute(request: SummarizeRequest) -> SummarizeResult:
        requests.append(request)
        return _result_for_request(request)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("sq")
        returned = run_summarize_tui(
            SummarizeRequest(context_locator="summary/context"),
            setup=_setup(),
            execute=execute,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == SummarizeTuiOutcome(
        (
            _result_for_request(SummarizeRequest(context_locator="summary/context")),
            _result_for_request(
                SummarizeRequest(
                    context_locator="summary/context",
                    include_descendants=True,
                    follow_embeds=True,
                )
            ),
        )
    )
    assert requests == [
        SummarizeRequest(context_locator="summary/context"),
        SummarizeRequest(
            context_locator="summary/context",
            include_descendants=True,
            follow_embeds=True,
        ),
    ]


def test_summarize_tui_cancels_before_execution() -> None:
    requests: list[SummarizeRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_summarize_tui(
            SummarizeRequest(context_locator="summary/context"),
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []


def test_summarize_tui_stages_descendants_independently_from_context() -> None:
    requests: list[SummarizeRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Z\x1b[Csq")
        returned = run_summarize_tui(
            SummarizeRequest(context_locator="summary/context"),
            setup=_setup_with_range(initial_range_mode="EXACT"),
            execute=lambda request: requests.append(request)
            or _result_for_request(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == SummarizeTuiOutcome(
        (
            _result_for_request(
                SummarizeRequest(
                    context_locator="summary/context",
                    include_descendants=True,
                    follow_embeds=True,
                )
            ),
        )
    )
    assert requests == [
        SummarizeRequest(
            context_locator="summary/context",
            include_descendants=True,
            follow_embeds=True,
        )
    ]


def test_summarize_empty_summary_runs_one_step_after_the_context() -> None:
    requests: list[SummarizeRequest] = []
    with create_pipe_input() as pipe_input:
        # Context owns first focus. Tab moves once to the empty Summary action,
        # where Enter performs the explicit run.
        pipe_input.send_text("\t\rq")
        returned = run_summarize_tui(
            SummarizeRequest(context_locator="summary/context"),
            setup=_setup_with_range(initial_range_mode="EXACT"),
            execute=lambda request: requests.append(request)
            or _result_for_request(request),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == SummarizeTuiOutcome(
        (_result_for_request(SummarizeRequest(context_locator="summary/context")),)
    )
    assert requests == [SummarizeRequest(context_locator="summary/context")]


def test_summarize_tui_stages_a_different_readable_context() -> None:
    requests: list[SummarizeRequest] = []
    other_result = SummarizeResult(
        context_name="other",
        include_descendants=False,
        follow_embeds=False,
        source_digest="b" * 64,
        source_count=0,
        understanding=UnderstandingSummary(
            text="The selected Context contains no ordinary Memories to summarize.",
            source_uids=(),
        ),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[A sq")
        returned = run_summarize_tui(
            SummarizeRequest(context_locator="summary/context"),
            setup=_setup_with_range(
                "other",
                "summary/context",
                initial_range_mode="EXACT",
            ),
            execute=lambda request: requests.append(request) or other_result,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == SummarizeTuiOutcome((other_result,))
    assert requests == [SummarizeRequest(context_locator="other")]


def test_summarize_tui_reruns_after_changing_descendants_from_result() -> None:
    requests: list[SummarizeRequest] = []

    def execute(request: SummarizeRequest) -> SummarizeResult:
        requests.append(request)
        return _result_for_request(request)

    with create_pipe_input() as pipe_input:
        # First run opens the result-focused workbench. Two Shift-Tabs cross
        # Context to reach the descendants control above it.
        pipe_input.send_text("s\x1b[Z\x1b[Z\x1b[Csq")
        returned = run_summarize_tui(
            SummarizeRequest(context_locator="summary/context"),
            setup=_setup_with_range(initial_range_mode="EXACT"),
            execute=execute,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.result_for(include_descendants=True) is not None
    assert requests == [
        SummarizeRequest(context_locator="summary/context"),
        SummarizeRequest(
            context_locator="summary/context",
            include_descendants=True,
            follow_embeds=True,
        ),
    ]


def test_summarize_both_outcome_keeps_direct_and_recursive_views_visible() -> None:
    outcome = SummarizeTuiOutcome(
        (
            _result_for_request(SummarizeRequest(context_locator="summary/context")),
            _result(),
        )
    )

    document = project_summarize_outcome(outcome)
    rendered = "".join(text for _style, text in document.render(focused_uid=None))

    assert "STATUS · BOTH VIEWS" in rendered
    assert "[CURRENT ONLY]" in rendered
    assert "STATUS · DIRECT · SOURCES 1" in rendered
    assert "[CURRENT + DESCENDANTS]" in rendered
    assert "STATUS · RECURSIVE · SOURCES 3" in rendered


def test_summarize_clipboard_projects_current_scope_and_complete_document() -> None:
    outcome = SummarizeTuiOutcome(
        (
            _result_for_request(SummarizeRequest(context_locator="summary/context")),
            _result(),
        )
    )

    direct = project_summarize_clipboard(
        outcome,
        focused_uid="SUMMARY:DIRECT:UNDERSTANDING",
        whole_document=False,
    )
    recursive = project_summarize_clipboard(
        outcome,
        focused_uid="SUMMARY:RECURSIVE:UNDERSTANDING",
        whole_document=False,
    )
    header = project_summarize_clipboard(
        outcome,
        focused_uid="SUMMARY:TITLE",
        whole_document=False,
    )
    status = project_summarize_clipboard(
        outcome,
        focused_uid="SUMMARY:STATUS",
        whole_document=False,
    )
    complete = project_summarize_clipboard(outcome, whole_document=True)

    assert direct.label == "current-only summary"
    assert direct.text.startswith("[CURRENT ONLY]\nThe Context records")
    assert "[CURRENT + DESCENDANTS]" not in direct.text
    assert recursive.label == "current + descendants summary"
    assert recursive.text.startswith("[CURRENT + DESCENDANTS]\nThe Context records")
    assert "[CURRENT ONLY]" not in recursive.text
    assert header == complete
    assert status == complete
    assert complete.label == "complete summary"
    assert "[CURRENT ONLY]" in complete.text
    assert "[CURRENT + DESCENDANTS]" in complete.text


def test_summarize_y_and_uppercase_y_copy_scope_then_complete_document() -> None:
    copied: list[str] = []

    with create_pipe_input() as pipe_input:
        # S runs both scopes. At the shared title, y copies the complete
        # document. Scoped sections narrow y; Y remains complete everywhere.
        pipe_input.send_text(
            "sy" + "\x1b[B" * 2 + "y" + "\x1b[B" * 3 + "yYq"
        )
        returned = run_summarize_tui(
            SummarizeRequest(context_locator="summary/context"),
            setup=_setup(),
            execute=_result_for_request,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert "[CURRENT ONLY]" in copied[0]
    assert "[CURRENT + DESCENDANTS]" in copied[0]
    assert copied[1].startswith("[CURRENT ONLY]\nThe Context records")
    assert "[CURRENT + DESCENDANTS]" not in copied[1]
    assert copied[2].startswith("[CURRENT + DESCENDANTS]\nThe Context records")
    assert "[CURRENT ONLY]" not in copied[2]
    assert "[CURRENT ONLY]" in copied[3]
    assert "[CURRENT + DESCENDANTS]" in copied[3]


def test_summarize_both_does_not_publish_a_partial_pair() -> None:
    requests: list[SummarizeRequest] = []

    def execute(request: SummarizeRequest) -> SummarizeResult:
        requests.append(request)
        if request.include_descendants:
            raise RuntimeError("recursive summary failed")
        return _result_for_request(request)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("s")
        with pytest.raises(RuntimeError, match="recursive summary failed"):
            run_summarize_tui(
                SummarizeRequest(context_locator="summary/context"),
                setup=_setup(),
                execute=execute,
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

    assert requests == [
        SummarizeRequest(context_locator="summary/context"),
        SummarizeRequest(
            context_locator="summary/context",
            include_descendants=True,
            follow_embeds=True,
        ),
    ]
