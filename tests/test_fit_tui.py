"""Typed projection and shared Viewer interaction for Fit."""

from __future__ import annotations

from dataclasses import replace

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.fit import (
    FIT_RULESET_VERSION,
    FIT_SCHEMA_VERSION,
    FitExample,
    FitJudgment,
    FitReport,
    FitRule,
)
from memcommit.fit_coherence import (
    FitCoherenceFinding,
    FitCoherenceReport,
    FitCoherenceSubject,
    FitContextFrame,
    plan_coherence_checks,
)
from memcommit.fit_application import FitPropositionsResult, FitResult
from memcommit.fit_judgment import (
    FitAnalysis,
    FitAssessment,
    FitProposition,
    FitQuestion,
)
from memcommit.interfaces.fit import fit_result_text
from memcommit.interfaces.tui.operations.fit import (
    project_proposition_fit_clipboard,
    project_proposition_fit_result,
    project_fit_clipboard,
    project_fit_result,
    run_proposition_fit_tui,
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


def _coherent_result(*, current: bool = True) -> FitResult:
    legacy = _result(current=current).report
    contexts = (
        FitContextFrame(
            "00000000-0000-0000-0000-000000000020",
            "k1",
            "ticker/raw",
            "RAW_EVIDENCE",
            "b" * 64,
            (),
        ),
        FitContextFrame(
            "00000000-0000-0000-0000-000000000021",
            "k2",
            "ticker/examples",
            "WORKING_CANDIDATES",
            "c" * 64,
            (),
        ),
        FitContextFrame(
            "00000000-0000-0000-0000-000000000022",
            "k3",
            "ticker/output",
            "PUBLICATION_TARGET",
            "d" * 64,
            (),
        ),
    )
    subjects = (
        FitCoherenceSubject(
            legacy.ground_uid,
            "g1",
            "GOAL",
            "Learn Rules for real United States company tickers.",
            ("k1", "k2", "k3"),
        ),
        FitCoherenceSubject(
            RULE_UID,
            "r1",
            "RULE",
            legacy.rules[0].statement,
            ("k3",),
        ),
        FitCoherenceSubject(
            FIT_EXAMPLE_UID,
            "e1",
            "EXAMPLE",
            legacy.examples[0].statement,
            ("k1", "k2", "k3"),
        ),
        FitCoherenceSubject(
            ISSUE_EXAMPLE_UID,
            "e2",
            "EXAMPLE",
            legacy.examples[1].statement,
            ("k1", "k2", "k3"),
        ),
    )
    checks = plan_coherence_checks(subjects, contexts)
    findings = []
    for check in checks:
        status = "FIT"
        material = ()
        reason = "The frozen relation stays coherent."
        if check.check_id == "context:e2":
            status = "UNDERDETERMINED"
            material = ("e2", "k2")
            reason = "The Example has no source-grounded real-company evidence."
        elif check.check_id == "vertical:goal-examples":
            status = "CONTRADICTS"
            material = ("g1", "e2")
            reason = "The unverified Example does not exercise the real-company Goal."
        findings.append(
            FitCoherenceFinding(
                check.check_id,
                check.axis,
                check.relation,
                status,
                check.subject_aliases,
                check.context_aliases,
                material,
                reason,
            )
        )
    coherence = FitCoherenceReport(
        brief="Refine ticker Rules against real sourced company Examples.",
        requirements=("ticker/output · publish reviewed Rules · minimum 1",),
        contexts=contexts,
        subjects=subjects,
        findings=tuple(findings),
        overview="One Example needs contextual and vertical review.",
        created_at="2026-08-16T12:00:00Z",
    )
    report = replace(
        legacy,
        coherence=coherence,
        schema_version=FIT_SCHEMA_VERSION,
        ruleset_version=FIT_RULESET_VERSION,
    )
    return FitResult(report, current)


def _proposition_result(*, verdict="MAY") -> FitPropositionsResult:
    question = FitQuestion(
        "fit",
        (
            FitProposition("goal", "Keep an entrance usable.", "GOAL"),
            FitProposition("rule", "The entrance closes at five.", "RULE"),
        ),
        (FitProposition("context", "There are two entrances.", "MEMORY"),),
    )
    return FitPropositionsResult(
        FitAnalysis(
            uid="00000000-0000-0000-0000-000000000010",
            question=question,
            assessment=FitAssessment(
                question_id="fit",
                verdict=verdict,
                reason="The referent changes whether the constraints conflict.",
                considered_proposition_ids=("context", "goal", "rule"),
                material_proposition_ids=("context", "goal", "rule"),
                consistent_reading=(
                    "A different entrance remains usable." if verdict == "MAY" else ""
                ),
                inconsistent_reading=(
                    "The only required entrance closes." if verdict == "MAY" else ""
                ),
            ),
            overview="The ordinary readings divide.",
            created_at="2026-08-15T12:00:00Z",
        )
    )


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


def test_unified_fit_projects_context_goal_rule_and_example_detection() -> None:
    result = _coherent_result()
    document = project_fit_result(result)
    rendered = "".join(
        text for _style, text in document.render(focused_uid="FIT:SUMMARY")
    )
    complete = project_fit_clipboard(result, whole_document=True)

    assert [section.kind for section in document.sections] == [
        "SUMMARY",
        "CONTEXT K",
        "GOAL",
        "RULE",
        "EXAMPLE",
        "EXAMPLE",
    ]
    assert "! ticker · 6/9 checks · CONTEXT 1 · VERTICAL 2 · PEER 0" in rendered
    assert "k1 · RAW_EVIDENCE · ticker/raw" in complete.text
    assert "! g1 · Learn Rules for real" in complete.text
    assert "! e2 · Axiom AI Technologies" in complete.text
    assert "CONTEXT · UNDERDETERMINED" in complete.text
    assert "VERTICAL · CONTRADICTS" in complete.text


def test_general_fit_projects_complete_inputs_and_may_readings() -> None:
    result = _proposition_result()
    document = project_proposition_fit_result(result)
    rendered = "".join(
        text for _style, text in document.render(focused_uid="FIT:JUDGMENT")
    )
    complete = project_proposition_fit_clipboard(result, whole_document=True)

    assert [section.uid for section in document.sections] == [
        "FIT:JUDGMENT",
        "FIT:INPUTS",
        "FIT:READINGS",
    ]
    assert "? MAY" in rendered
    assert "BACKGROUND · context · MEMORY" in complete.text
    assert "PROPOSITION · goal · GOAL" in complete.text
    assert "CONSISTENT READING" in complete.text
    assert "INCONSISTENT READING" in complete.text


def test_general_fit_viewer_y_and_uppercase_y_copy_focused_then_complete() -> None:
    copied: list[str] = []
    result = _proposition_result()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("yYq")
        returned = run_proposition_fit_tui(
            result,
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == result
    assert copied[0].startswith("? MAY")
    assert "PROPOSITION · goal" not in copied[0]
    assert copied[1].startswith("? MAY")
    assert "PROPOSITION · goal · GOAL" in copied[1]
    assert "INCONSISTENT READING" in copied[1]
