from __future__ import annotations

import json
import uuid

import pytest

from memcommit.fit import (
    FitError,
    FitExample,
    FitReport,
    FitRule,
    fit_ground_examples,
)


def _uid() -> str:
    return str(uuid.uuid4())


class _Provider:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.prompt = ""
        self.operation = ""

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.prompt = prompt
        self.operation = operation
        return json.dumps(self.response)


def _rule(statement: str = "Use the first four letters in uppercase.") -> FitRule:
    return FitRule(_uid(), "r1", statement)


def test_exact_output_fit_withholds_expected_and_converts_failure() -> None:
    rule = _rule()
    example = FitExample(
        _uid(),
        "e1",
        "Axiom AI Technologies -> AAT",
        "EXACT_OUTPUT",
        (rule.uid,),
        input_text="Axiom AI Technologies",
        expected_output="AAT",
    )
    provider = _Provider(
        {
            "overview": "The rule yields four letters.",
            "predictions": [
                {
                    "case_id": "e1",
                    "disposition": "PREDICTED",
                    "predicted": "AXIO",
                    "reason": "The rule explicitly selects four letters.",
                }
            ],
        }
    )
    report = fit_ground_examples(
        ground_uid=_uid(),
        ground_name="ticker",
        ground_revision=3,
        ground_digest="a" * 64,
        rules=(rule,),
        examples=(example,),
        provider=provider,
    )

    assert report.judgments[0].status == "CONTRADICTS"
    assert report.judgments[0].observed == "AXIO"
    assert '"expected"' not in provider.prompt
    assert "AAT" not in provider.prompt
    assert FitReport.from_dict(report.to_dict()) == report


def test_proposition_fit_accounts_for_observation_counterexample() -> None:
    rule = _rule("The sky is always blue.")
    example = FitExample(
        _uid(),
        "e1",
        "On August 15 the sky was yellow.",
        "PROPOSITION",
        (rule.uid,),
    )
    provider = _Provider(
        {
            "overview": "The observation conflicts with the universal claim.",
            "judgments": [
                {
                    "example_id": "e1",
                    "status": "CONTRADICTS",
                    "reason": "One yellow observation refutes always blue.",
                }
            ],
        }
    )
    report = fit_ground_examples(
        ground_uid=_uid(),
        ground_name="sky",
        ground_revision=1,
        ground_digest="b" * 64,
        rules=(rule,),
        examples=(example,),
        provider=provider,
    )

    assert report.judgments[0].status == "CONTRADICTS"
    assert provider.operation == "fit_ground_propositions"
    assert "Do not invent a cause" in provider.prompt


def test_fit_rejects_mixed_projection_and_incomplete_coverage() -> None:
    rule = _rule()
    exact = FitExample(
        _uid(), "e1", "Apple -> APPL", "EXACT_OUTPUT", (rule.uid,),
        input_text="Apple", expected_output="APPL",
    )
    proposition = FitExample(
        _uid(), "e2", "Apple maps to APPL.", "PROPOSITION", (rule.uid,)
    )
    with pytest.raises(FitError, match="cannot mix"):
        fit_ground_examples(
            ground_uid=_uid(),
            ground_name="ticker",
            ground_revision=1,
            ground_digest="c" * 64,
            rules=(rule,),
            examples=(exact, proposition),
            provider=_Provider({}),
        )

    with pytest.raises(FitError, match="omitted"):
        fit_ground_examples(
            ground_uid=_uid(),
            ground_name="ticker",
            ground_revision=1,
            ground_digest="c" * 64,
            rules=(rule,),
            examples=(proposition,),
            provider=_Provider({"overview": "none", "judgments": []}),
        )
