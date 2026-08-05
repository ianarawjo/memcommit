from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from memcommit.eval.operation_gate_campaign import (
    DEFAULT_OPERATION_GATE_FIXTURE,
    DEFAULT_OPERATION_GATE_V2_FIXTURE,
    load_operation_gate_corpus,
    load_operation_gate_composite_lock,
    load_operation_gate_lock,
    run_operation_gate_campaign,
)
from memcommit.eval.semantic_campaign import SemanticCampaignError
from memcommit.provider_types import ProviderIdentity
from memcommit.operation_gate_pipeline import classify_operation_gate
from memcommit.operation_gate_pipeline import OperationGateError


class FakeProvider:
    identity = ProviderIdentity(provider="ollama", model="qwen-test")
    timeout = 10.0
    context_tokens = 4096
    max_output_tokens = 64
    thinking = False
    last_run = None


class ExpectedClassifier:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, case, provider, **kwargs):
        self.calls.append((case, kwargs))
        label = case["expected"]["label"]
        raw = json.dumps({"label": label})
        return SimpleNamespace(
            classification=SimpleNamespace(label=label),
            raw_response=raw,
            prompt_digest="a" * 64,
            schema_digest="b" * 64,
            response_digest="c" * 64,
        )


class ResponseProvider(FakeProvider):
    def __init__(self, response: str) -> None:
        self.response = response
        self.schemas = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.schemas.append(output_schema)
        return self.response


def test_reviewed_gate_fixture_covers_operations_tasks_and_length_tiers():
    corpus = load_operation_gate_corpus()
    lock = load_operation_gate_lock()

    assert len(corpus.cases) == 37
    assert corpus.case_limit == 200
    assert set(corpus.definitions) == {
        "conflict", "atomize", "translate", "compare", "update",
        "ground", "meld", "forget", "integrate",
    }
    assert {case["task"] for case in corpus.cases} == {1, 2, 3}
    assert {case["length_tier"] for case in corpus.cases} == {"SHORT", "LONG"}
    assert (lock.digest, lock.case_count, lock.case_limit) == (
        corpus.digest, len(corpus.cases), corpus.case_limit
    )


def test_gate_campaign_filters_and_never_leaks_held_expectation(tmp_path):
    classifier = ExpectedClassifier()

    ledger = run_operation_gate_campaign(
        FakeProvider(),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "ledger",
        provider_connection_seconds=0.25,
        runs=1,
        fixture_path=DEFAULT_OPERATION_GATE_FIXTURE,
        operations=["conflict"],
        length_tiers=["SHORT"],
        classifier=classifier,
    )

    assert ledger["summary"]["cases"] == {"passed": 4, "failed": 0, "total": 4}
    assert ledger["summary"]["distributions"]["by_operation"] == {
        "conflict": {"passed": 4, "total": 4}
    }
    for held, kwargs in classifier.calls:
        examples = kwargs["calibration_examples"]
        assert held["id"] not in {example["id"] for example in examples}
        assert all(set(example["expected"]) == {"label"} for example in examples)
        assert all("rationale" not in example["expected"] for example in examples)


def test_gate_fixture_rejects_more_than_declared_200_case_boundary(tmp_path):
    value = json.loads(DEFAULT_OPERATION_GATE_FIXTURE.read_text(encoding="utf-8"))
    value["case_limit"] = 201
    fixture = tmp_path / "gates.json"
    fixture.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(SemanticCampaignError, match="between 1 and 200"):
        load_operation_gate_corpus(fixture)


def test_gate_fixture_changed_after_freeze_is_rejected(tmp_path):
    value = json.loads(DEFAULT_OPERATION_GATE_FIXTURE.read_text(encoding="utf-8"))
    value["description"] += " changed"
    fixture = tmp_path / DEFAULT_OPERATION_GATE_FIXTURE.name
    fixture.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(SemanticCampaignError, match="frozen calibration lock"):
        load_operation_gate_corpus(fixture, verify_lock=True)


def test_v2_extension_composes_with_frozen_base_without_copying_it():
    baseline = load_operation_gate_corpus()
    corpus = load_operation_gate_corpus(DEFAULT_OPERATION_GATE_V2_FIXTURE)

    assert len(baseline.cases) == 37
    assert len(corpus.cases) == 75
    assert [case["id"] for case in corpus.cases[:37]] == [
        case["id"] for case in baseline.cases
    ]
    assert sum(case["length_tier"] == "SHORT" for case in corpus.cases) == 57
    assert sum(case["length_tier"] == "LONG" for case in corpus.cases) == 18
    lock = load_operation_gate_composite_lock()
    assert (lock.composite_digest, lock.case_count, lock.base_case_count) == (
        corpus.digest, len(corpus.cases), len(baseline.cases)
    )


def test_v2_extension_changed_after_freeze_is_rejected(tmp_path):
    value = json.loads(DEFAULT_OPERATION_GATE_V2_FIXTURE.read_text(encoding="utf-8"))
    value["description"] += " changed"
    fixture = tmp_path / DEFAULT_OPERATION_GATE_V2_FIXTURE.name
    fixture.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(SemanticCampaignError, match="composite.*frozen calibration lock"):
        load_operation_gate_corpus(fixture, verify_lock=True)


def test_gate_campaign_can_select_new_extension_cases(tmp_path):
    classifier = ExpectedClassifier()
    case_ids = ["translate-v2-unknown-source", "ground-v2-fact"]

    ledger = run_operation_gate_campaign(
        FakeProvider(),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "ledger",
        provider_connection_seconds=0.0,
        fixture_path=DEFAULT_OPERATION_GATE_V2_FIXTURE,
        case_ids=case_ids,
        classifier=classifier,
    )

    assert ledger["corpus"]["fixture_case_count"] == 75
    assert ledger["corpus"]["selected_case_ids"] == case_ids
    assert ledger["summary"]["cases"] == {"passed": 2, "failed": 0, "total": 2}


def test_gate_campaign_selects_only_additions_layer(tmp_path):
    ledger = run_operation_gate_campaign(
        FakeProvider(),  # type: ignore[arg-type]
        ledger_dir=tmp_path / "ledger",
        provider_connection_seconds=0.0,
        fixture_path=DEFAULT_OPERATION_GATE_V2_FIXTURE,
        layer="additions",
        classifier=ExpectedClassifier(),
    )

    assert ledger["corpus"]["selected_layer"] == "ADDITIONS"
    assert ledger["corpus"]["base_case_count"] == 37
    assert ledger["summary"]["cases"] == {"passed": 38, "failed": 0, "total": 38}


def test_conflict_gate_projects_unresolved_scope_to_may():
    corpus = load_operation_gate_corpus()
    case = next(case for case in corpus.cases if case["id"] == "conflict-short-may")
    definition = corpus.definitions["conflict"]
    provider = ResponseProvider(
        '{"scope_relation":"UNRESOLVED","claim_relation":"INCOMPATIBLE"}'
    )

    result = classify_operation_gate(
        case,
        provider,  # type: ignore[arg-type]
        operation="conflict",
        instruction=definition.instruction,
        labels=definition.labels,
        calibration_examples=[],
    )

    assert result.classification.label == "MAY"
    assert set(provider.schemas[0]["properties"]) == {
        "scope_relation", "claim_relation"
    }


@pytest.mark.parametrize(
    ("case_id", "operation", "response", "expected", "schema_fields"),
    [
        (
            "translate-v2-unknown-source",
            "translate",
            '{"source_resolution":"UNRESOLVED","resolved_label":"CONTRADICTED"}',
            "UNKNOWN",
            {"source_resolution", "resolved_label"},
        ),
        (
            "compare-v2-unknown-referent",
            "compare",
            '{"scope_resolution":"UNRESOLVED","resolved_label":"DISTINCT"}',
            "UNKNOWN",
            {"scope_resolution", "resolved_label"},
        ),
        (
            "meld-v2-unknown-entrance",
            "meld",
            '{"scope_resolution":"UNRESOLVED","resolved_label":"UNKNOWN"}',
            "UNKNOWN",
            {"scope_resolution", "resolved_label"},
        ),
    ],
)
def test_unknown_capable_gates_project_resolution_evidence(
    case_id, operation, response, expected, schema_fields
):
    corpus = load_operation_gate_corpus(DEFAULT_OPERATION_GATE_V2_FIXTURE)
    case = next(case for case in corpus.cases if case["id"] == case_id)
    definition = corpus.definitions[operation]
    provider = ResponseProvider(response)

    result = classify_operation_gate(
        case,
        provider,  # type: ignore[arg-type]
        operation=operation,
        instruction=definition.instruction,
        labels=definition.labels,
        calibration_examples=[],
    )

    assert result.classification.label == expected
    assert set(provider.schemas[0]["properties"]) == schema_fields


def test_meld_gate_rejects_unknown_sentinel_with_resolved_scope():
    corpus = load_operation_gate_corpus(DEFAULT_OPERATION_GATE_V2_FIXTURE)
    case = next(case for case in corpus.cases if case["id"] == "meld-v2-unknown-entrance")
    definition = corpus.definitions["meld"]
    provider = ResponseProvider(
        '{"scope_resolution":"RESOLVED","resolved_label":"UNKNOWN"}'
    )

    with pytest.raises(OperationGateError, match="resolved scope"):
        classify_operation_gate(
            case,
            provider,  # type: ignore[arg-type]
            operation="meld",
            instruction=definition.instruction,
            labels=definition.labels,
            calibration_examples=[],
        )
