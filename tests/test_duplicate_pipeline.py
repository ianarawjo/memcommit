"""Strict host-first duplicate-relation pipeline contracts."""
from __future__ import annotations

import json

import pytest

from memcommit.application.capabilities.semantic.classification.duplicates import (
    DUPLICATE_PIPELINE_V1,
    DuplicatePipelineError,
    classify_duplicate_case,
)


def _case(left: str, right: str, relation: str = "DISTINCT") -> dict:
    return {
        "id": "candidate",
        "scenario": "Two Memories are compared inside one local Context.",
        "memories": [
            {"uid": "left", "content": left},
            {"uid": "right", "content": right},
        ],
        "expected": {"relation": relation, "rationale": "must not leak"},
    }


class FakeProvider:
    def __init__(self, response: str = '{"relation":"DISTINCT"}') -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return self.response


def test_exact_and_surface_relations_are_host_only():
    provider = FakeProvider()

    exact = classify_duplicate_case(
        _case("same", "same", "EXACT"),
        provider,  # type: ignore[arg-type]
        calibration_examples=[],
    )
    surface = classify_duplicate_case(
        _case("  same   words ", "same words", "SURFACE_EQUIVALENT"),
        provider,  # type: ignore[arg-type]
        calibration_examples=[],
    )

    assert exact.classification.relation == "EXACT"
    assert exact.stage == "HOST_EXACT"
    assert surface.classification.relation == "SURFACE_EQUIVALENT"
    assert surface.stage == "HOST_SURFACE_EQUIVALENT"
    assert provider.calls == []


def test_semantic_stage_projects_out_held_expected_contract():
    provider = FakeProvider('{"relation":"SEMANTIC_EQUIVALENT"}')
    calibration = [
        {
            "id": "example",
            "scenario": "Reviewed example",
            "memories": [
                {"uid": "a", "content": "A"},
                {"uid": "b", "content": "B"},
            ],
            "expected": {"relation": "OVERLAP"},
        }
    ]

    run = classify_duplicate_case(
        _case("The office opens at nine.", "The office starts admitting at 9."),
        provider,  # type: ignore[arg-type]
        calibration_examples=calibration,
    )

    assert run.pipeline_id == DUPLICATE_PIPELINE_V1
    assert run.classification.relation == "SEMANTIC_EQUIVALENT"
    prompt = provider.calls[0][0]
    assert "must not leak" not in prompt
    assert '"relation":"OVERLAP"' in prompt
    schema = provider.calls[0][2]
    assert schema["properties"]["relation"]["enum"] == [  # type: ignore[index]
        "SEMANTIC_EQUIVALENT",
        "OVERLAP",
        "UNKNOWN",
        "DISTINCT",
    ]


@pytest.mark.parametrize(
    ("raw", "category"),
    [
        ('{"relation":"DISTINCT","extra":true}', "SCHEMA"),
        ('{"relation":"DISTINCT","relation":"OVERLAP"}', "INVALID_JSON"),
        ("not-json", "INVALID_JSON"),
        ("", "EMPTY_OR_TRUNCATED"),
    ],
)
def test_semantic_output_fails_closed(raw, category):
    provider = FakeProvider(raw)

    with pytest.raises(DuplicatePipelineError) as caught:
        classify_duplicate_case(
            _case("left", "right"),
            provider,  # type: ignore[arg-type]
            calibration_examples=[],
        )

    assert caught.value.category == category
    assert caught.value.prompt_digest is not None
    assert caught.value.schema_digest is not None


def test_host_result_is_replayable_strict_json():
    run = classify_duplicate_case(
        _case("same", "same", "EXACT"),
        FakeProvider(),  # type: ignore[arg-type]
        calibration_examples=[],
    )

    assert json.loads(run.raw_response) == {"relation": "EXACT"}
    assert len(run.prompt_digest) == len(run.schema_digest) == 64
