"""Typed projection and interaction contracts for the Summarize TUI."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.interfaces.tui.operations.summarize import (
    project_summarize_result,
    run_summarize_tui,
)
from memcommit.summarize_application import SummarizeResult
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
    assert "READ-ONLY · RECURSIVE · SOURCES 3" in rendered
    assert "WHAT MEM UNDERSTOOD" in rendered
    assert "closure and its staff exception" in rendered


def test_summarize_tui_navigates_and_closes_without_operation_effects() -> None:
    result = _result()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\x1b[B\x1b[A\x7f")
        document = run_summarize_tui(
            result,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert document == project_summarize_result(result)
