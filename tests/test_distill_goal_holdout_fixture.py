"""Prompt-unseen Goal-contract cases for cumulative Distill evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from memcommit.application.capabilities.semantic.generative_reduction_reference import (
    render_distill_elaborate_reference_examples,
)


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "src" / "memcommit" / "application" / "capabilities" / "evaluation"
    / "fixtures"
    / "distill_goal_holdout.json"
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_distill_goal_holdout_freezes_all_accumulated_goal_modes() -> None:
    fixture = _fixture()

    assert fixture["schema_version"] == 1
    assert fixture["corpus_role"] == "HOLDOUT"
    assert fixture["independent_holdout"] is True
    assert fixture["prompt_reference"] is False
    sources = {source["id"]: source for source in fixture["sources"]}
    assert set(sources) == {"coffee-freshness-rules", "korean-cafe-reviews"}
    assert len(sources["coffee-freshness-rules"]["memories"]) == 4
    assert len(sources["korean-cafe-reviews"]["memories"]) == 5
    assert [case["id"] for case in fixture["cases"]] == [
        "coffee-semantic-goal",
        "review-semantic-topology-goal",
        "review-reproduction-goal",
        "review-operational-criteria-goal",
    ]
    for case in fixture["cases"]:
        assert case["source_id"] in sources
        assert case["goal"].strip()
        assert case["required_readings"]


def test_distill_goal_holdout_answers_never_enter_prompt_reference() -> None:
    fixture = _fixture()
    prompt_reference = render_distill_elaborate_reference_examples()

    for case in fixture["cases"]:
        assert case["id"] not in prompt_reference
        assert case["goal"] not in prompt_reference
        for reading in case["required_readings"]:
            assert reading not in prompt_reference
