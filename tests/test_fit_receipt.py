"""Compact, issue-only Fit receipt projection."""

from __future__ import annotations

from dataclasses import replace

import click
from click.testing import CliRunner

from memcommit.fit import FitExample, FitJudgment, FitReport, FitRule
from memcommit.fit_application import FitInputOrigin, FitPropositionsResult, FitResult
from memcommit.fit_judgment import (
    FitAnalysis,
    FitAssessment,
    FitProposition,
    FitQuestion,
)
from memcommit.fit_coherence import FitCoherenceFinding
from memcommit.interfaces.cli.fit import (
    render_fit_plain,
    render_proposition_fit_plain,
)
from memcommit.interfaces.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.interfaces.fit import (
    _coherence_participant_label,
    fit_result_text,
    proposition_fit_result_text,
)


RULE_UID = "11111111-1111-1111-1111-111111111111"
FIT_UID = "22222222-2222-2222-2222-222222222222"
MAY_UID = "33333333-3333-3333-3333-333333333333"
NO_UID = "44444444-4444-4444-4444-444444444444"


def _result(*, current: bool = True) -> FitResult:
    report = FitReport(
        uid="00000000-0000-0000-0000-000000000005",
        ground_uid="00000000-0000-0000-0000-000000000006",
        ground_name="ticker",
        ground_revision=7,
        ground_digest="a" * 64,
        rules=(FitRule(RULE_UID, "r1", "Use one stable abbreviation."),),
        examples=(
            FitExample(
                FIT_UID,
                "e1",
                "Apple Inc. may be represented as AAPL.",
                "PROPOSITION",
                (RULE_UID,),
            ),
            FitExample(
                MAY_UID,
                "e2",
                "Axiom AI Technologies may be AAT or AAIT.",
                "PROPOSITION",
                (RULE_UID,),
            ),
            FitExample(
                NO_UID,
                "e3",
                "The same symbol must be both AAT and AXAI.",
                "PROPOSITION",
                (RULE_UID,),
            ),
        ),
        judgments=(
            FitJudgment(
                FIT_UID,
                "FIT",
                (RULE_UID,),
                "The abbreviation follows the Rule.",
                "AAPL",
            ),
            FitJudgment(
                MAY_UID,
                "UNDERDETERMINED",
                (RULE_UID,),
                "The Rule does not choose between the two abbreviations.",
                "AAT or AAIT",
            ),
            FitJudgment(
                NO_UID,
                "CONTRADICTS",
                (RULE_UID,),
                "One exact symbol cannot have both values.",
                "AAT and AXAI",
            ),
        ),
        overview="One passes, one is conditional, and one conflicts.",
        created_at="2026-08-21T12:00:00Z",
    )
    return FitResult(report, current)


def test_fit_receipt_prints_only_may_and_no_details() -> None:
    text = fit_result_text(_result())

    assert text.splitlines() == [
        "FIT · NO · [GROUND CONTEXT ticker] · 1/3",
        "? MAY · [RULE r1] [MEMORY 11111111] Use one stable abbreviation. ↔ "
        "[EXAMPLE e2] [MEMORY 33333333] Axiom AI Technologies may be AAT or AAIT.",
        "! NO · [RULE r1] [MEMORY 11111111] Use one stable abbreviation. ↔ "
        "[EXAMPLE e3] [MEMORY 44444444] The same symbol must be both AAT and AXAI.",
    ]
    assert "e1" not in text
    assert "AAPL" not in text


def test_fit_receipt_uses_may_when_no_check_is_no() -> None:
    original = _result().report
    report = replace(
        original,
        examples=original.examples[:2],
        judgments=original.judgments[:2],
    )

    assert fit_result_text(FitResult(report, True)).splitlines()[0] == (
        "FIT · MAY · [GROUND CONTEXT ticker] · 1/2"
    )


def test_stale_fit_receipt_does_not_repeat_old_issue_details() -> None:
    assert fit_result_text(_result(current=False)) == (
        "FIT · STALE · [GROUND CONTEXT ticker] · 1/3"
    )


def _proposition_result(verdict: str) -> FitPropositionsResult:
    question = FitQuestion(
        "fit",
        (
            FitProposition("p1", "The main entrance closes at five."),
            FitProposition("p2", "The main entrance stays open until ten."),
        ),
    )
    assessment = FitAssessment(
        question_id="fit",
        verdict=verdict,  # type: ignore[arg-type]
        reason="The ordinary readings conflict unless entrance scope changes.",
        considered_proposition_ids=("p1", "p2"),
        material_proposition_ids=("p1", "p2"),
        consistent_reading=(
            "The second statement refers to a separate staff entrance."
            if verdict == "MAY"
            else ""
        ),
        inconsistent_reading=(
            "Both statements refer to the same main entrance."
            if verdict == "MAY"
            else ""
        ),
    )
    return FitPropositionsResult(
        FitAnalysis(
            uid="00000000-0000-0000-0000-000000000010",
            question=question,
            assessment=assessment,
            overview="The complete frozen set was judged once.",
            created_at="2026-08-21T12:00:00Z",
        )
    )


def test_general_no_receipt_names_and_shows_both_material_propositions() -> None:
    assert proposition_fit_result_text(_proposition_result("NO")) == (
        "FIT · NO · [PROPOSITION p1] The main entrance closes at five. ↔ "
        "[PROPOSITION p2] The main entrance stays open until ten."
    )


def test_general_may_receipt_is_one_line_but_typed_readings_remain() -> None:
    result = _proposition_result("MAY")

    assert proposition_fit_result_text(result) == (
        "FIT · MAY · [PROPOSITION p1] The main entrance closes at five. ↔ "
        "[PROPOSITION p2] The main entrance stays open until ten."
    )
    assert result.analysis.assessment.consistent_reading
    assert result.analysis.assessment.inconsistent_reading


def test_general_receipt_projects_three_typed_operands_as_one_operator() -> None:
    question = FitQuestion(
        "fit",
        (
            FitProposition("m1", "Claim from Context A.", "MEMORY"),
            FitProposition("m2", "One directly selected claim.", "MEMORY"),
            FitProposition("p1", "One literal claim."),
        ),
    )
    result = FitPropositionsResult(
        FitAnalysis(
            uid="00000000-0000-0000-0000-000000000020",
            question=question,
            assessment=FitAssessment(
                question_id="fit",
                verdict="YES",
                reason="The three operands can jointly hold.",
                considered_proposition_ids=("m1", "m2", "p1"),
                material_proposition_ids=(),
            ),
            overview="The complete frozen set was judged once.",
            created_at="2026-08-21T12:00:00Z",
        ),
        input_origins=(
            FitInputOrigin(
                alias="m1",
                kind="CONTEXT",
                context_name="context-a",
                context_uid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                memory_uid="11111111-1111-1111-1111-111111111111",
            ),
            FitInputOrigin(
                alias="m2",
                kind="MEMORY",
                context_name="context-b",
                context_uid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                memory_uid="22222222-2222-2222-2222-222222222222",
            ),
        ),
    )

    assert proposition_fit_result_text(result) == (
        "FIT · YES · [CONTEXT context-a] [MEMORY 11111111] "
        "Claim from Context A. ↔ [MEMORY 22222222] "
        "One directly selected claim. ↔ [PROPOSITION p1] One literal claim."
    )


@click.command()
def _render_ground_receipt() -> None:
    render_fit_plain(_result())


@click.command()
def _render_general_receipt() -> None:
    render_proposition_fit_plain(_proposition_result("YES"))


def test_cli_colors_only_typed_judgments_and_preserves_plain_text() -> None:
    runner = CliRunner()
    ground_color = runner.invoke(_render_ground_receipt, color=True)
    ground_plain = runner.invoke(_render_ground_receipt, color=False)
    general_color = runner.invoke(_render_general_receipt, color=True)

    assert ground_color.exit_code == 0
    assert ground_plain.exit_code == 0
    assert general_color.exit_code == 0
    assert click.unstyle(ground_color.output) == ground_plain.output
    assert ground_plain.output == f"{fit_result_text(_result())}\n"
    assert (
        click.style(
            "MAY",
            fg=semantic_color_rgb(SemanticColorRole.JUDGMENT_MAY),
            bold=True,
        )
        in ground_color.output
    )
    assert (
        click.style(
            "NO",
            fg=semantic_color_rgb(SemanticColorRole.JUDGMENT_NO),
            bold=True,
        )
        in ground_color.output
    )
    assert (
        click.style(
            "YES",
            fg=semantic_color_rgb(SemanticColorRole.JUDGMENT_YES),
            bold=True,
        )
        in general_color.output
    )
    assert "\x1b[" not in ground_plain.output


def test_no_color_environment_retains_the_exact_receipt_text() -> None:
    output = CliRunner().invoke(
        _render_ground_receipt,
        color=None,
        env={"NO_COLOR": "1"},
    )

    assert output.exit_code == 0
    assert output.output == f"{fit_result_text(_result())}\n"
    assert "\x1b[" not in output.output


def test_coherence_heading_keeps_both_check_sides_when_material_is_one() -> None:
    finding = FitCoherenceFinding(
        check_id="context:e1",
        axis="CONTEXT",
        relation="CONTEXT_EXAMPLE",
        status="UNDERDETERMINED",
        subject_aliases=("e1",),
        context_aliases=("k1",),
        material_aliases=("e1",),
        reason="The Context side supplies no matching evidence.",
    )

    assert _coherence_participant_label(finding) == "e1 ↔ k1"
