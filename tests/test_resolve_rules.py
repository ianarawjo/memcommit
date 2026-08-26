"""Exact authored Resolve rule and canonical-case regressions."""

from __future__ import annotations

from pathlib import Path

from memcommit.resolve_rules import (
    RESOLVE_RULESET_VERSION,
    resolve_ruleset,
    resolve_ruleset_prompt_payload,
)


def _case(case_id: str) -> dict[str, object]:
    ruleset = resolve_ruleset()
    return next(
        case
        for case in ruleset["cases"]
        if isinstance(case, dict) and case["id"] == case_id
    )


def test_every_authored_rule_and_exact_case_enters_the_production_prompt() -> None:
    authored = resolve_ruleset()
    prompt = resolve_ruleset_prompt_payload()

    assert prompt["ruleset_version"] == RESOLVE_RULESET_VERSION
    assert prompt["rules"] == authored["rules"]
    assert prompt["cases"] == authored["cases"]


def test_focused_matrix_names_every_authored_rule_and_case() -> None:
    authored = resolve_ruleset()
    matrix = (
        Path(__file__).parents[1]
        / "agent-records"
        / "docs"
        / "resolve-application-boundary-matrix.md"
    ).read_text(encoding="utf-8")

    for rule in authored["rules"]:
        assert isinstance(rule, dict)
        assert f"`{rule['id']}`" in matrix
    for case in authored["cases"]:
        assert isinstance(case, dict)
        assert f"`{case['id']}`" in matrix


def test_opening_time_case_freezes_one_exact_alternative_update() -> None:
    case = _case("opening-time-safe-alternative")

    assert case["source"] == [
        {"id": "m1", "content": "The office opens at 8.", "mutable": True},
        {"id": "m2", "content": "The office opens at 9.", "mutable": True},
    ]
    assert case["expected"] == {
        "classification": "SAFE_ALTERNATIVE",
        "outcome": "RESOLVE",
        "resolution_level": "MAY",
        "post_fit": "MAY_OR_YES",
        "effects": [
            {
                "kind": "UPDATE",
                "target_id": "m2",
                "before": "The office opens at 9.",
                "after": ("The office opens at 9 as an alternative to opening at 8."),
                "source_ids": ["m1", "m2"],
            }
        ],
        "result": [
            "The office opens at 8.",
            "The office opens at 9 as an alternative to opening at 8.",
        ],
        "rule_ids": [
            "R01_WHOLE_FRAME",
            "R02_DEFAULT_REMOVE_NO",
            "R05_SAFE_ALTERNATIVE",
            "R06_NO_INVENTED_DISCRIMINATOR",
            "R07_NO_ARBITRARY_PRIORITY",
            "R10_NO_DELETE_FOR_FIT",
            "R11_EXACT_POSTCHECK",
        ],
        "reason": (
            "One relation-bearing edit preserves both recorded times and leaves "
            "their applicability unresolved."
        ),
    }


def test_consequential_choice_case_freezes_no_effects_and_exact_source() -> None:
    case = _case("payment-account-choice-stops")
    expected = case["expected"]
    assert isinstance(expected, dict)

    assert expected["classification"] == "CHOICE_REQUIRED"
    assert expected["outcome"] == "STOP"
    assert expected["resolution_level"] == "NO"
    assert expected["post_fit"] == "NO"
    assert expected["effects"] == []
    assert expected["result"] == [
        "Send the payment to account A.",
        "Send the payment to account B.",
    ]
