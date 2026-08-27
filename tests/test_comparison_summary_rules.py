"""Compact Compare calibration and strict receipt boundaries."""

from __future__ import annotations

import json

import pytest

import memcommit.application.ops as ops
from memcommit.application.operations.compare.ledger.model import ComparisonInput
from memcommit.application.operations.compare.summary import ComparisonSummaryError
from memcommit.application.operations.compare.summary_provider import summarize_comparison
from memcommit.application.operations.compare.summary_rules import (
    COMPARISON_SUMMARY_RULESET_VERSION,
    COMPARISON_SUMMARY_WORD_LIMIT,
    comparison_summary_ruleset,
)


class ResponseProvider:
    def __init__(self, response_factory):
        self.response_factory = response_factory
        self.prompts: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.prompts.append(prompt)
        payload = json.loads(prompt.split("COMPARISON SUMMARY PAYLOAD:\n", 1)[1])
        return json.dumps(self.response_factory(payload))


def _pair(*, focused: bool = False) -> ComparisonInput:
    reference = ops.init("rules/reference")
    reference_focus = ops.add(reference, "Complete the opening in two sentences.")
    ops.add(reference, "Use descriptive headings.")
    compared = ops.init("rules/compared")
    compared_focus = ops.add(compared, "Allow a third sentence when context is needed.")
    ops.add(compared, "Use connected paragraphs.")
    return ComparisonInput.from_contexts(
        reference,
        compared,
        reference_memory_selector=reference_focus.uid if focused else None,
        compared_memory_selector=compared_focus.uid if focused else None,
    )


def _primary_ids(payload: dict[str, object]) -> tuple[list[str], list[str]]:
    frames = payload["frames"]
    assert isinstance(frames, list)
    result: list[list[str]] = []
    for frame in frames:
        assert isinstance(frame, dict)
        memories = frame["memories"]
        assert isinstance(memories, list)
        result.append(
            [
                str(row["id"])
                for row in memories
                if isinstance(row, dict) and row["role"] == "PRIMARY"
            ]
        )
    return result[0], result[1]


def test_complete_versioned_ruleset_enters_every_provider_turn():
    provider = ResponseProvider(
        lambda payload: {
            "text": "Both rules prioritize an immediate opening, but they use different sentence bounds.",
            "source_ids": [ids[0] for ids in _primary_ids(payload)],
        }
    )

    summarize_comparison(_pair(), provider)

    payload = json.loads(
        provider.prompts[0].split("COMPARISON SUMMARY PAYLOAD:\n", 1)[1]
    )
    assert payload["ruleset"] == {
        "ruleset_version": COMPARISON_SUMMARY_RULESET_VERSION,
        "rules": comparison_summary_ruleset()["rules"],
        "cases": comparison_summary_ruleset()["cases"],
    }
    assert payload["length"] == {
        "limit": COMPARISON_SUMMARY_WORD_LIMIT,
        "unit": "words",
    }


def test_summary_rejects_provider_aliases_in_human_prose():
    def response(payload):
        reference_ids, compared_ids = _primary_ids(payload)
        return {
            "text": f"Both rules concern an opening [{compared_ids[0]}].",
            "source_ids": [reference_ids[0], compared_ids[0]],
        }

    with pytest.raises(ComparisonSummaryError, match="private source alias"):
        summarize_comparison(_pair(), ResponseProvider(response))


def test_summary_rejects_more_than_the_word_limit_without_clipping():
    def response(payload):
        reference_ids, compared_ids = _primary_ids(payload)
        return {
            "text": " ".join(["word"] * (COMPARISON_SUMMARY_WORD_LIMIT + 1)),
            "source_ids": [reference_ids[0], compared_ids[0]],
        }

    with pytest.raises(ComparisonSummaryError, match="word limit"):
        summarize_comparison(_pair(), ResponseProvider(response))


def test_focused_summary_must_cite_both_selected_primary_memories():
    def response(payload):
        frames = payload["frames"]
        assert isinstance(frames, list)
        context_ids = [
            str(
                next(
                    row["id"]
                    for row in frame["memories"]
                    if row["role"] == "CONTEXT"
                )
            )
            for frame in frames
        ]
        return {
            "text": "The neighboring structure rules differ.",
            "source_ids": context_ids,
        }

    with pytest.raises(ComparisonSummaryError, match="PRIMARY evidence"):
        summarize_comparison(_pair(focused=True), ResponseProvider(response))


def test_ruleset_covers_small_asymmetric_and_boundary_shapes():
    cases = comparison_summary_ruleset()["cases"]
    assert isinstance(cases, list)
    assert {case["id"] for case in cases} == {
        "selected-number-condition",
        "rule-to-instances",
        "temporary-override-baseline",
        "general-policy-specialization",
        "different-governance-directions",
    }
