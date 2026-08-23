"""Read-only report and compact-browser contracts for quality finders."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.ops as ops
from memcommit.commands.quality_find_workbench import (
    run_quality_find_resolution_workbench,
)
from memcommit.findings import (
    AmbiguityFinding,
    AmbiguityReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.interfaces.tui.workbenches.findings.document import (
    quality_finding_compact_text,
)
from memcommit.quality_find_workbench import (
    create_quality_find_workbench,
    quality_find_report_view,
)
from memcommit.quality_find_report import (
    QualityFindBrowserReceipt,
    QualityFindReportError,
)


def _source():
    context = ops.init("quality/report")
    first = ops.add(context, "Reports are due within 30 days.")
    second = ops.add(context, "Submit reports no later than one month.")
    return context, first, second


def test_ambiguity_report_exposes_readings_without_answer_contract() -> None:
    context, first, _second = _source()
    session = create_quality_find_workbench(
        "ambiguities",
        context,
        AmbiguityReport(
            memory_count=2,
            findings=(
                AmbiguityFinding(
                    memory=first,
                    interpretation="DOMINANT",
                    clarification="REQUIRED",
                    ordinary_readings=(
                        "Thirty days after the event.",
                        "Thirty days after discovery.",
                    ),
                    reason="The starting event is not named.",
                    question="Which event starts the deadline?",
                ),
            ),
        ),
    )

    view = quality_find_report_view(session, context)
    item = view.items[0]

    assert view.operation == "FIND AMBIGUITIES"
    assert item.classification == "DOMINANT · CLARIFICATION REQUIRED"
    assert [reading.label for reading in item.readings] == [
        "DOMINANT",
        "ALTERNATIVE",
    ]
    assert item.follow_up == "Which event starts the deadline?"
    assert not hasattr(item, "options")
    assert not hasattr(item, "obligation")
    assert not hasattr(item, "response_state")
    assert session.responses == {}

    paragraph = quality_finding_compact_text(item)
    assert "SOURCE MEMORY · quality/report" in paragraph
    assert "Reports are due within 30 days." in paragraph
    assert "WHY THIS IS UNCLEAR · The starting event is not named." in paragraph
    assert "QUESTION · Which event starts the deadline?" in paragraph
    assert "DOMINANT: Thirty days after the event." in paragraph
    assert "ALTERNATIVE: Thirty days after discovery." in paragraph
    assert paragraph.count("\n") == 1


def test_finding_browser_root_close_never_creates_response_state() -> None:
    context, first, _second = _source()
    session = create_quality_find_workbench(
        "ambiguities",
        context,
        AmbiguityReport(
            memory_count=2,
            findings=(
                AmbiguityFinding(
                    memory=first,
                    interpretation="SINGLE",
                    clarification="OPTIONAL",
                    ordinary_readings=("Thirty days after the event.",),
                    reason="The deadline has one ordinary reading.",
                    question="",
                ),
            ),
        ),
    )

    with create_pipe_input() as pipe_input:
        # Enter is inert because a Find ambiguity has no answer or detail mode.
        pipe_input.send_text("\r\x1b")
        returned = run_quality_find_resolution_workbench(
            session,
            context,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is session
    assert session.responses == {}


def test_dedun_handoff_receives_all_eligible_report_evidence_without_confirmation(
) -> None:
    context, first, second = _source()
    third = ops.add(context, "Reports can be delivered whenever convenient.")
    session = create_quality_find_workbench(
        "duplicates",
        context,
        DuplicateReport(
            memory_count=3,
            findings=(
                DuplicateFinding(
                    first,
                    second,
                    "SEMANTIC_EQUIVALENT",
                    "The two deadlines are substitutable in this frame.",
                ),
                DuplicateFinding(
                    second,
                    third,
                    "OVERLAP",
                    "The delivery statements overlap but are not substitutes.",
                ),
            ),
        ),
    )
    received = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        run_quality_find_resolution_workbench(
            session,
            context,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            duplicate_handoff_handler=received.append,
        )

    assert len(received) == 1
    assert [item.classification for item in received[0]] == [
        "SEMANTIC_EQUIVALENT"
    ]
    assert session.responses == {}


def test_compact_finding_browser_never_enters_the_alternate_screen() -> None:
    path = (
        Path(__file__).parents[1]
        / "memcommit/interfaces/tui/workbenches/findings/screen.py"
    )
    module = ast.parse(path.read_text(encoding="utf-8"))
    application_calls = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "Application")
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "Application"
            )
        )
    ]

    assert len(application_calls) == 1
    full_screen = next(
        keyword.value
        for keyword in application_calls[0].keywords
        if keyword.arg == "full_screen"
    )
    assert isinstance(full_screen, ast.Constant)
    assert full_screen.value is False


def test_handoff_receipt_requires_one_exact_finding_target() -> None:
    with pytest.raises(
        QualityFindReportError,
        match="requires one exact target",
    ):
        QualityFindBrowserReceipt("HANDOFF")
