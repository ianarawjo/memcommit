"""Frozen prompt-unseen cases for Distill/Elaborate generalization."""

from __future__ import annotations

import json
from pathlib import Path

from memcommit.application.semantic.generative_reduction_reference import (
    render_distill_elaborate_reference_examples,
)


HOLDOUT_PATH = (
    Path(__file__).parents[1]
    / "src" / "memcommit"
    / "eval"
    / "fixtures"
    / "distill_elaborate_holdout.json"
)


def _holdout() -> dict[str, object]:
    return json.loads(HOLDOUT_PATH.read_text(encoding="utf-8"))


def test_distill_elaborate_holdout_is_independent_and_covers_four_boundaries() -> None:
    fixture = _holdout()

    assert fixture["schema_version"] == 1
    assert fixture["corpus_role"] == "HOLDOUT"
    assert fixture["independent_holdout"] is True
    assert fixture["prompt_reference"] is False
    cases = fixture["cases"]
    assert isinstance(cases, list)
    assert [case["id"] for case in cases] == [
        "mixed-subfamilies",
        "ordered-fibonacci-continuation",
        "cleanliness-operational-hierarchy",
        "cleanliness-diagnostic-hierarchy",
    ]
    for case in cases:
        assert case["distill_source_memories"]
        assert case["distill_required_readings"]
        assert case["elaborate_parent_memories"]
        assert case["elaborate_number"] > 0
        assert case["elaborate_required_readings"]


def test_holdout_answers_never_enter_the_packaged_prompt_reference() -> None:
    fixture = _holdout()
    prompt_reference = render_distill_elaborate_reference_examples()

    for case in fixture["cases"]:
        assert case["id"] not in prompt_reference
        for memory in case["elaborate_parent_memories"]:
            assert memory not in prompt_reference
        for reading in (
            *case["distill_required_readings"],
            *case["elaborate_required_readings"],
        ):
            assert reading not in prompt_reference
