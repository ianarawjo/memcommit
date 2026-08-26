"""Foundational role-neutral Fit judgment contracts."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.commands.fit.command as fit_command
from memcommit.cli import app
from memcommit.operations.fit.judgment import (
    FIT_JUDGMENT_PAYLOAD_MARKER,
    FitJudgmentError,
    FitProposition,
    FitQuestion,
    judge_fit,
    prepare_fit_judgments,
)
from memcommit.operations.fit.application import FitPropositionsRequest
from memcommit.operations.fit.runtime import run_proposition_fit


class FitProvider:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.prompt = ""
        self.operation = ""

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.prompt = prompt
        self.operation = operation
        assert output_schema is not None
        return json.dumps(self.response)


def _response(
    verdict: str,
    *,
    considered: list[str] | None = None,
    material: list[str] | None = None,
    consistent: str = "",
    inconsistent: str = "",
) -> dict[str, object]:
    return {
        "overview": "The complete frozen set was judged once.",
        "judgments": [
            {
                "question_id": "fit",
                "verdict": verdict,
                "reason": "The statements can jointly govern."
                if verdict == "YES"
                else "Their ordinary readings divide or conflict.",
                "considered_proposition_ids": considered or ["p1", "p2"],
                "material_proposition_ids": material
                or ([] if verdict == "YES" else ["p1", "p2"]),
                "consistent_reading": consistent,
                "inconsistent_reading": inconsistent,
            }
        ],
    }


def test_fit_judges_role_neutral_complete_set_with_common_sense_boundary() -> None:
    provider = FitProvider(_response("YES"))

    analysis = judge_fit(
        (
            FitProposition("p1", "Use the main entrance.", "GOAL"),
            FitProposition("p2", "The staff entrance remains open.", "RULE"),
        ),
        provider=provider,
    )

    assert analysis.assessment.verdict == "YES"
    assert analysis.assessment.considered_proposition_ids == ("p1", "p2")
    assert provider.operation == "fit_propositions"
    assert FIT_JUDGMENT_PAYLOAD_MARKER in provider.prompt
    assert "common-sense, and domain-convention prior" in provider.prompt
    assert "prior is not objective truth" in provider.prompt
    assert "if a competent ordinary reader read the complete frame" in provider.prompt
    assert (
        "practical reading judgment rather than formal theorem proving"
        in provider.prompt
    )
    assert "Do not test satisfiability over every imaginable world" in provider.prompt
    assert (
        "Do not invent one scenario merely to save or break the set" in provider.prompt
    )
    assert (
        "Ambiguity matters to Fit only when ordinary readings split" in provider.prompt
    )
    assert (
        "Different subjects, scopes, or unrelated propositions are YES"
        in provider.prompt
    )
    assert "Do not omit, rank, retrieve, generate, revise" in provider.prompt
    payload = json.loads(provider.prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
    assert [item["role"] for item in payload["questions"][0]["propositions"]] == [
        "GOAL",
        "RULE",
    ]


def test_fit_may_requires_real_consistent_and_inconsistent_readings() -> None:
    propositions = (
        FitProposition("p1", "The main entrance closes at five."),
        FitProposition("p2", "The entrance stays open until ten."),
    )
    provider = FitProvider(_response("MAY"))

    with pytest.raises(FitJudgmentError, match="must show both ordinary outcomes"):
        judge_fit(propositions, provider=provider)

    provider = FitProvider(
        _response(
            "MAY",
            consistent="The second statement refers to the staff entrance.",
            inconsistent="Both statements refer to the main entrance.",
        )
    )
    analysis = judge_fit(propositions, provider=provider)
    assert analysis.assessment.verdict == "MAY"


def test_fit_rejects_omitted_or_reordered_propositions() -> None:
    provider = FitProvider(_response("YES", considered=["p2", "p1"]))

    with pytest.raises(FitJudgmentError, match="omitted, duplicated, or reordered"):
        judge_fit(
            (
                FitProposition("p1", "One proposition."),
                FitProposition("p2", "Another proposition."),
            ),
            provider=provider,
        )


def test_fit_validates_and_budgets_before_provider_construction() -> None:
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return FitProvider(_response("YES"))

    with pytest.raises(ValueError, match="at least two propositions"):
        run_proposition_fit(
            FitPropositionsRequest(
                propositions=(FitProposition("p1", "Only one proposition."),)
            ),
            provider_factory=provider_factory,
        )
    assert calls == 0


def test_prepare_fit_accepts_empty_background_but_not_one_subject() -> None:
    with pytest.raises(FitJudgmentError, match="at least two propositions"):
        FitQuestion(
            "fit",
            (FitProposition("p1", "One proposition."),),
            (FitProposition("k1", "A frozen background proposition."),),
        )

    prepared = prepare_fit_judgments(
        (
            FitQuestion(
                "fit",
                (
                    FitProposition("p1", "One proposition."),
                    FitProposition("p2", "Another proposition."),
                ),
            ),
        )
    )
    assert prepared.questions[0].background == ()
    serialized_schema = json.dumps(prepared.output_schema)
    assert "oneOf" not in serialized_schema
    assert "uniqueItems" not in serialized_schema


def test_mem_fit_accepts_two_literal_propositions_and_prints_yes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        fit_command,
        "connect_semantic_provider",
        lambda: FitProvider(_response("YES")),
    )

    result = CliRunner().invoke(
        app,
        ["fit", "The main entrance closes.", "The staff entrance opens.", "--plain"],
        color=True,
    )

    assert result.exit_code == 0, result.output
    assert "\x1b[" not in result.output
    assert result.output == "FIT · YES · [TARGETS: PROPOSITION p1, p2]\n"


def test_mem_fit_requires_two_operands_and_explicit_ground_mode() -> None:
    one = CliRunner().invoke(app, ["fit", "Only one proposition.", "--plain"])
    mixed = CliRunner().invoke(
        app,
        ["fit", "A", "B", "--ground", "ticker", "--plain"],
    )

    assert one.exit_code == 1
    assert "at least two propositions" in one.output
    assert mixed.exit_code == 1
    assert "proposition operands or --ground" in mixed.output
