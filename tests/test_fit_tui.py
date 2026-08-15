"""Typed projection and shared Viewer interaction for Fit."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.fit import FitExample, FitJudgment, FitReport, FitRule
from memcommit.fit_application import FitResult
from memcommit.interfaces.fit import fit_result_text
from memcommit.interfaces.tui.operations.fit import (
    project_fit_clipboard,
    project_fit_result,
    run_fit_tui,
)


RULE_UID = "00000000-0000-0000-0000-000000000001"
FIT_EXAMPLE_UID = "00000000-0000-0000-0000-000000000002"
ISSUE_EXAMPLE_UID = "00000000-0000-0000-0000-000000000003"


def _result(*, current: bool = True) -> FitResult:
    report = FitReport(
        uid="00000000-0000-0000-0000-000000000004",
        ground_uid="00000000-0000-0000-0000-000000000005",
        ground_name="ticker",
        ground_revision=7,
        ground_digest="a" * 64,
        rules=(FitRule(RULE_UID, "r1", "Use a stable ticker abbreviation."),),
        examples=(
            FitExample(
                FIT_EXAMPLE_UID,
                "e1",
                "Apple Inc. may be represented as AAPL.",
                "PROPOSITION",
                (RULE_UID,),
            ),
            FitExample(
                ISSUE_EXAMPLE_UID,
                "e2",
                "Axiom AI Technologies may be represented as AAT or AAIT.",
                "PROPOSITION",
                (RULE_UID,),
            ),
        ),
        judgments=(
            FitJudgment(
                FIT_EXAMPLE_UID,
                "FIT",
                (RULE_UID,),
                "The abbreviation follows the Rule.",
                "AAPL",
            ),
            FitJudgment(
                ISSUE_EXAMPLE_UID,
                "UNDERDETERMINED",
                (RULE_UID,),
                "The Rule does not choose between two valid abbreviations.",
                "AAT or AAIT",
            ),
        ),
        overview="One Example fits and one needs a more specific Rule.",
        created_at="2026-08-15T12:00:00Z",
    )
    return FitResult(report, current)


def test_fit_projects_typed_result_with_stable_example_sections() -> None:
    document = project_fit_result(_result())

    assert [section.uid for section in document.sections] == [
        "FIT:SUMMARY",
        f"FIT:EXAMPLE:{FIT_EXAMPLE_UID}",
        f"FIT:EXAMPLE:{ISSUE_EXAMPLE_UID}",
    ]
    rendered = "".join(text for _style, text in document.render(focused_uid=None))
    assert "! ticker · 1/2" in rendered
    assert "✓ e1 · Apple Inc." in rendered
    assert "! e2 · Axiom AI Technologies" in rendered
    assert "UNDERDETERMINED · The Rule does not choose" in rendered
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert "RECEIPT" not in rendered


def test_fit_clipboard_uses_typed_focused_and_complete_projections() -> None:
    result = _result()

    focused = project_fit_clipboard(
        result,
        focused_uid=f"FIT:EXAMPLE:{ISSUE_EXAMPLE_UID}",
        whole_document=False,
    )
    complete = project_fit_clipboard(result, whole_document=True)

    assert focused.label == "Fit Example e2"
    assert focused.text.startswith("! e2 · Axiom AI Technologies")
    assert "UNDERDETERMINED · The Rule does not choose" in focused.text
    assert "✓ e1" not in focused.text
    assert complete.label == "complete Fit result"
    assert complete.text.startswith(fit_result_text(result) + "\n\n✓ e1")
    assert "! e2" in complete.text
    assert "WHAT MEM UNDERSTOOD" not in complete.text


def test_fit_viewer_y_and_uppercase_y_copy_focused_then_complete() -> None:
    copied: list[str] = []
    result = _result()

    with create_pipe_input() as pipe_input:
        # The Viewer begins at SUMMARY. Move to the first Example, copy it, then
        # copy the complete report without changing semantic focus.
        pipe_input.send_text("\x1b[ByYq")
        returned = run_fit_tui(
            result,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == result
    assert copied[0].startswith("✓ e1 · Apple Inc.")
    assert "! e2" not in copied[0]
    assert copied[1].startswith("! ticker · 1/2\n\n✓ e1")
    assert "! e2" in copied[1]


def test_fit_stale_state_replaces_prior_judgment_marks() -> None:
    result = _result(current=False)
    rendered = "".join(
        text
        for _style, text in project_fit_result(result).render(
            focused_uid="FIT:SUMMARY"
        )
    )
    focused = project_fit_clipboard(
        result,
        focused_uid=f"FIT:EXAMPLE:{ISSUE_EXAMPLE_UID}",
        whole_document=False,
    )

    assert "◷ ticker · 1/2" in rendered
    assert "◷ e1" in rendered
    assert "◷ e2" in rendered
    assert "UNDERDETERMINED" not in rendered
    assert focused.text.startswith("◷ e2")
    assert "UNDERDETERMINED" not in focused.text
