"""Dense ambiguity-stage contracts for provider-neutral campaigns."""
from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from memcommit.ambiguity_pipeline import (
    AMBIGUITY_PIPELINE_V1,
    AMBIGUITY_PIPELINE_V2,
    AMBIGUITY_PIPELINE_V3,
    AMBIGUITY_PIPELINE_V4,
    AMBIGUITY_PIPELINE_V5,
    AMBIGUITY_PIPELINE_V6,
    AmbiguityClassification,
    AmbiguityPipelineError,
    classify_ambiguity_case,
    classify_ambiguity_case_v1,
    classify_ambiguity_case_v3,
    classify_ambiguity_case_v4,
    classify_ambiguity_case_v5,
    classify_ambiguity_case_v6,
)


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "src" / "memcommit"
    / "application"
    / "evaluation"
    / "fixtures"
    / "ambiguity.json"
)
PAYLOAD_MARKER = "AMBIGUITY CLASSIFICATION PAYLOAD:\n"


class FakeProvider:
    def __init__(self, response: object):
        self.response = response
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return self.response


class SequenceProvider(FakeProvider):
    def __init__(self, responses: list[str]):
        super().__init__(None)
        self.responses = list(responses)

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls.append((prompt, operation, output_schema))
        return self.responses.pop(0)


def _case() -> dict[str, object]:
    return {
        "id": "target",
        "scenario": "A hotel reservation has no preceding referent.",
        "memory": {"uid": "target-memory", "content": "It's 216."},
        "expected": {
            "interpretation": "COMPETING",
            "clarification": "REQUIRED",
            "rationale": "TARGET EXPECTED MUST NOT LEAK",
        },
    }


def test_classifies_once_with_exact_schema_and_replay_artifacts():
    raw = '{\n  "interpretation": "COMPETING", "clarification": "REQUIRED"\n}'
    provider = FakeProvider(raw)

    run = classify_ambiguity_case(
        _case(),
        provider,  # type: ignore[arg-type]
        calibration_examples=[
            {
                "scenario": "One defined entrance is in scope.",
                "memory": {"uid": "example", "content": "It closes at 5."},
                "expected": {
                    "interpretation": "SINGLE",
                    "clarification": "NONE",
                },
            }
        ],
    )

    assert run.classification == AmbiguityClassification(
        interpretation="COMPETING",
        clarification="REQUIRED",
    )
    assert run.raw_response == raw
    assert len(provider.calls) == 1
    prompt, operation, schema = provider.calls[0]
    assert operation == "ambiguity classification"
    assert schema == {
        "type": "object",
        "properties": {
            "interpretation": {
                "type": "string",
                "enum": ["SINGLE", "DOMINANT", "COMPETING"],
            },
            "clarification": {
                "type": "string",
                "enum": ["NONE", "HELPFUL", "REQUIRED"],
            },
        },
        "required": ["interpretation", "clarification"],
        "additionalProperties": False,
    }
    assert run.prompt_digest == hashlib.sha256(prompt.encode()).hexdigest()
    canonical_schema = json.dumps(
        schema,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert run.schema_digest == hashlib.sha256(
        canonical_schema.encode()
    ).hexdigest()
    assert run.response_digest == hashlib.sha256(raw.encode()).hexdigest()
    assert run.pipeline_id == AMBIGUITY_PIPELINE_V2
    assert run.pipeline_version == 2


def test_v1_replay_and_v2_current_prompt_have_distinct_identity():
    raw = '{"interpretation":"SINGLE","clarification":"NONE"}'
    v1 = classify_ambiguity_case_v1(
        _case(),
        FakeProvider(raw),  # type: ignore[arg-type]
        calibration_examples=[],
    )
    v2 = classify_ambiguity_case(
        _case(),
        FakeProvider(raw),  # type: ignore[arg-type]
        calibration_examples=[],
    )

    assert (v1.pipeline_id, v1.pipeline_version) == (AMBIGUITY_PIPELINE_V1, 1)
    assert (v2.pipeline_id, v2.pipeline_version) == (AMBIGUITY_PIPELINE_V2, 2)
    assert v1.prompt_digest != v2.prompt_digest
    assert v1.schema_digest == v2.schema_digest


def test_v3_composes_four_binary_probes_and_projects_stage_calibration():
    provider = SequenceProvider(
        [
            '{"answer":"YES"}',
            '{"answer":"NO"}',
            '{"answer":"YES"}',
            '{"answer":"YES"}',
        ]
    )
    calibration = [
        {
            "id": "single-none",
            "scenario": "One reading.",
            "memory": {"uid": "s", "content": "One."},
            "expected": {"interpretation": "SINGLE", "clarification": "NONE"},
        },
        {
            "id": "dominant-required",
            "scenario": "One reading leads.",
            "memory": {"uid": "d", "content": "Leading."},
            "expected": {
                "interpretation": "DOMINANT",
                "clarification": "REQUIRED",
            },
        },
        {
            "id": "competing-helpful",
            "scenario": "Two balanced readings.",
            "memory": {"uid": "c", "content": "Balanced."},
            "expected": {
                "interpretation": "COMPETING",
                "clarification": "HELPFUL",
            },
        },
    ]

    run = classify_ambiguity_case_v3(
        _case(),
        provider,  # type: ignore[arg-type]
        calibration_examples=calibration,
    )

    assert run.classification == AmbiguityClassification(
        interpretation="COMPETING",
        clarification="HELPFUL",
    )
    assert (run.pipeline_id, run.pipeline_version) == (AMBIGUITY_PIPELINE_V3, 3)
    assert [stage.stage for stage in run.stage_runs] == [
        "MULTIPLE_READINGS",
        "CLEAR_LEADER",
        "PRACTICAL_IMPROVEMENT",
        "CAN_PROCEED",
    ]
    assert all(stage.completion_seconds >= 0 for stage in run.stage_runs)
    payloads = [
        json.loads(call[0].split(PAYLOAD_MARKER, 1)[1])
        for call in provider.calls
    ]
    assert all("expected" not in payload["candidate"] for payload in payloads)
    assert [
        len(payload["calibration_examples"]) for payload in payloads
    ] == [3, 2, 3, 2]
    assert {
        example["expected"]["answer"]
        for example in payloads[1]["calibration_examples"]
    } == {"YES", "NO"}


def test_v3_skips_conditional_probes_for_single_none():
    provider = SequenceProvider(
        ['{"answer":"NO"}', '{"answer":"NO"}']
    )

    run = classify_ambiguity_case_v3(
        _case(),
        provider,  # type: ignore[arg-type]
        calibration_examples=[],
    )

    assert run.classification == AmbiguityClassification(
        interpretation="SINGLE",
        clarification="NONE",
    )
    assert [stage.stage for stage in run.stage_runs] == [
        "MULTIPLE_READINGS",
        "PRACTICAL_IMPROVEMENT",
    ]


def test_v4_projects_two_evidence_censuses_into_public_labels():
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "primary_reading": "Show a physical permit.",
                    "alternative_reading": "Show accepted electronic proof.",
                    "structure": "MULTIPLE_WITH_LEADER",
                }
            ),
            json.dumps(
                {
                    "missing_detail": "Which proof format is accepted?",
                    "effect": "BLOCKS_OR_MATERIAL_RISK",
                }
            ),
        ]
    )
    calibration = [
        {
            "id": "single-none",
            "scenario": "One defined place.",
            "memory": {"uid": "s", "content": "It closes at five."},
            "expected": {
                "interpretation": "SINGLE",
                "clarification": "NONE",
                "ordinary_readings": ["The place closes at five."],
                "question": "",
            },
        },
        {
            "id": "competing-helpful",
            "scenario": "Two responsible roles.",
            "memory": {"uid": "c", "content": "Ask the person in charge."},
            "expected": {
                "interpretation": "COMPETING",
                "clarification": "HELPFUL",
                "ordinary_readings": ["Ask role A.", "Ask role B."],
                "question": "Which responsible role is intended?",
            },
        },
    ]

    run = classify_ambiguity_case_v4(
        _case(),
        provider,  # type: ignore[arg-type]
        calibration_examples=calibration,
    )

    assert run.classification == AmbiguityClassification(
        interpretation="DOMINANT",
        clarification="REQUIRED",
    )
    assert (run.pipeline_id, run.pipeline_version) == (AMBIGUITY_PIPELINE_V4, 4)
    assert [stage.stage for stage in run.stage_runs] == [
        "READING_CENSUS",
        "CLARIFICATION_CENSUS",
    ]
    assert run.stage_runs[0].evidence == {
        "primary_reading": "Show a physical permit.",
        "alternative_reading": "Show accepted electronic proof.",
        "structure": "MULTIPLE_WITH_LEADER",
    }
    payloads = [
        json.loads(call[0].split(PAYLOAD_MARKER, 1)[1])
        for call in provider.calls
    ]
    assert payloads[0]["calibration_examples"][1]["expected"] == {
        "primary_reading": "Ask role A.",
        "alternative_reading": "Ask role B.",
        "structure": "MULTIPLE_BALANCED",
    }
    assert payloads[1]["calibration_examples"][0]["expected"] == {
        "missing_detail": "",
        "effect": "NO_IMPROVEMENT",
    }


def test_v4_rejects_inconsistent_census_shape():
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "primary_reading": "One reading.",
                    "alternative_reading": "Contradictory extra reading.",
                    "structure": "ONE",
                }
            )
        ]
    )

    with pytest.raises(AmbiguityPipelineError) as caught:
        classify_ambiguity_case_v4(
            _case(),
            provider,  # type: ignore[arg-type]
            calibration_examples=[],
        )

    assert caught.value.category == "SCHEMA"
    assert caught.value.stage == "READING_CENSUS"


def test_v5_contrast_checklist_has_distinct_replay_identity():
    responses = [
        json.dumps(
            {
                "primary_reading": "One ordinary reading.",
                "alternative_reading": "",
                "structure": "ONE",
            }
        ),
        json.dumps(
            {"missing_detail": "", "effect": "NO_IMPROVEMENT"}
        ),
    ]
    v4_provider = SequenceProvider(list(responses))
    v5_provider = SequenceProvider(list(responses))
    v6_provider = SequenceProvider(list(responses))

    v4 = classify_ambiguity_case_v4(
        _case(),
        v4_provider,  # type: ignore[arg-type]
        calibration_examples=[],
    )
    v5 = classify_ambiguity_case_v5(
        _case(),
        v5_provider,  # type: ignore[arg-type]
        calibration_examples=[],
    )
    v6 = classify_ambiguity_case_v6(
        _case(),
        v6_provider,  # type: ignore[arg-type]
        calibration_examples=[],
    )

    assert (v5.pipeline_id, v5.pipeline_version) == (AMBIGUITY_PIPELINE_V5, 5)
    assert v4.prompt_digest != v5.prompt_digest
    assert "contrast checklist" in v5_provider.calls[0][0]
    assert (v6.pipeline_id, v6.pipeline_version) == (AMBIGUITY_PIPELINE_V6, 6)
    assert v5.prompt_digest != v6.prompt_digest
    assert "electronic or alternate proof" in v6_provider.calls[0][0]
    assert "MINOR_FRICTION rather than NO_IMPROVEMENT" in v6_provider.calls[1][0]


def test_real_fixture_supports_leave_one_out_without_expected_answer_leak():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    target = next(
        case
        for case in fixture["cases"]
        if case["id"] == "competing-required-hotel-216"
    )
    calibration = [
        case for case in fixture["cases"] if case["id"] != target["id"]
    ]
    provider = FakeProvider(
        '{"interpretation":"COMPETING","clarification":"REQUIRED"}'
    )

    classify_ambiguity_case(
        target,
        provider,  # type: ignore[arg-type]
        calibration_examples=calibration,
    )

    prompt = provider.calls[0][0]
    payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
    assert payload["candidate"] == {
        "scenario": target["scenario"],
        "memory": target["memory"],
    }
    assert payload["calibration_examples"] == calibration
    assert "expected" not in payload["candidate"]
    assert target["expected"]["rationale"] not in prompt
    assert target not in payload["calibration_examples"]


def test_calibration_examples_can_be_empty():
    provider = FakeProvider(
        '{"interpretation":"SINGLE","clarification":"NONE"}'
    )

    classify_ambiguity_case(
        _case(),
        provider,  # type: ignore[arg-type]
        calibration_examples=[],
    )

    payload = json.loads(provider.calls[0][0].split(PAYLOAD_MARKER, 1)[1])
    assert payload["calibration_examples"] == []


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "not json",
        '```json\n{"interpretation":"SINGLE","clarification":"NONE"}\n```',
        '{"interpretation":"SINGLE","clarification":"NONE"} trailing prose',
        "[]",
        '{"interpretation":"SINGLE"}',
        '{"interpretation":"SINGLE","clarification":"NONE","reason":"x"}',
        (
            '{"interpretation":"SINGLE","interpretation":"DOMINANT",'
            '"clarification":"NONE"}'
        ),
        '{"interpretation":"UNKNOWN","clarification":"NONE"}',
        '{"interpretation":"SINGLE","clarification":"OPTIONAL"}',
    ],
)
def test_rejects_malformed_or_non_exact_output(raw):
    provider = FakeProvider(raw)

    with pytest.raises(AmbiguityPipelineError):
        classify_ambiguity_case(
            _case(),
            provider,  # type: ignore[arg-type]
            calibration_examples=[],
        )

    assert len(provider.calls) == 1


def test_output_error_retains_failure_category_and_raw_response():
    raw = '{"interpretation":"SINGLE","clarification":"UNKNOWN"}'
    provider = FakeProvider(raw)

    with pytest.raises(AmbiguityPipelineError) as caught:
        classify_ambiguity_case(
            _case(),
            provider,  # type: ignore[arg-type]
            calibration_examples=[],
        )

    assert caught.value.category == "SCHEMA"
    assert caught.value.raw_response == raw
    assert caught.value.response_digest == hashlib.sha256(raw.encode()).hexdigest()
    assert caught.value.prompt_digest is not None
    assert caught.value.schema_digest is not None


@pytest.mark.parametrize(
    "case",
    [
        {"scenario": "", "memory": {"uid": "m", "content": "content"}},
        {"scenario": "scenario", "memory": {"uid": "m"}},
        {
            "scenario": "scenario",
            "memory": {"uid": "m", "content": "content", "extra": True},
        },
    ],
)
def test_rejects_invalid_candidate_before_provider_connection(case):
    provider = FakeProvider(
        '{"interpretation":"SINGLE","clarification":"NONE"}'
    )

    with pytest.raises(AmbiguityPipelineError):
        classify_ambiguity_case(
            case,
            provider,  # type: ignore[arg-type]
            calibration_examples=[],
        )

    assert provider.calls == []


def test_classification_and_run_are_frozen():
    provider = FakeProvider(
        '{"interpretation":"SINGLE","clarification":"HELPFUL"}'
    )
    run = classify_ambiguity_case(
        _case(),
        provider,  # type: ignore[arg-type]
        calibration_examples=[],
    )

    with pytest.raises(FrozenInstanceError):
        run.classification.interpretation = "COMPETING"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        run.raw_response = "{}"  # type: ignore[misc]
