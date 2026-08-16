from __future__ import annotations

import copy
import json

import pytest

from memcommit.comparison import ComparisonInput
from memcommit.context import Context, Memory
from memcommit.eval.compare_latency_ab import (
    BASELINE,
    COMPACT,
    CompareLatencyABError,
    build_task2_comparison_input,
    compact_output_schema,
    parse_compact_analysis,
    run_compare_latency_ab,
    write_benchmark_ledger,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


def _comparison_input() -> ComparisonInput:
    reference = Context(
        uid="74649d43-1807-45fe-9918-faf9cb24bd9d",
        name="advisor1",
    )
    compared = Context(
        uid="895d6f95-d6d7-4b58-93d6-bc650546bc22",
        name="advisor2",
    )
    reference.add(
        Memory(
            uid="3fa0a24d-80e5-4d1f-a9eb-dc88de0c98a4",
            content="Keep one operational claim.",
        )
    )
    reference.add(
        Memory(
            uid="2fd54ff0-38b0-4134-b6b7-b3c55528bc2d",
            content="Reference-only constraint.",
        )
    )
    compared.add(
        Memory(
            uid="d49b1ae9-d572-4af7-b464-93d4e42d686d",
            content="Keep one operational claim.",
        )
    )
    compared.add(
        Memory(
            uid="e57ab14e-f80a-4275-8f0d-7968a01f9029",
            content="Compared-only constraint.",
        )
    )
    return ComparisonInput.from_contexts(reference, compared)


def _compact_response() -> dict[str, object]:
    return {
        "reference_group_ids": [1, 2],
        "compared_group_ids": [1, 3],
        "groups": [
            {"kind": "EQUIVALENT", "note": ""},
            {"kind": "DISTINCT", "note": ""},
            {"kind": "DISTINCT", "note": ""},
        ],
        "issues": [],
    }


def test_compact_schema_keeps_fixed_vectors_and_omits_narrative_layers():
    schema = compact_output_schema(2, 3)

    properties = schema["properties"]
    assert set(properties) == {
        "reference_group_ids",
        "compared_group_ids",
        "groups",
        "issues",
    }
    assert properties["reference_group_ids"]["minItems"] == 2
    assert properties["reference_group_ids"]["maxItems"] == 2
    assert properties["compared_group_ids"]["minItems"] == 3
    assert properties["compared_group_ids"]["maxItems"] == 3
    assert "overview" not in properties
    assert "reports" not in properties
    assert "source_assignments" not in properties


def test_compact_response_reconstructs_exact_typed_analysis():
    comparison_input = _comparison_input()

    analysis = parse_compact_analysis(
        json.dumps(_compact_response()),
        comparison_input=comparison_input,
    )

    assert len(analysis.relations) == 3
    assert [relation.kind for relation in analysis.relations] == [
        "EQUIVALENT",
        "DISTINCT",
        "DISTINCT",
    ]
    assert sum(len(relation.members) for relation in analysis.relations) == 4
    assert analysis.reports is not None
    assert analysis.reports.both
    assert analysis.reports.reference_only
    assert analysis.reports.compared_only
    assert analysis.reports.differences == ""


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda value: value["reference_group_ids"].pop(),
            "exactly 2 rows",
        ),
        (
            lambda value: value["groups"].append(
                {"kind": "DISTINCT", "note": ""}
            ),
            "Every compact group must be used",
        ),
        (
            lambda value: value["groups"][0].update({"kind": "DISTINCT"}),
            "exactly one source side",
        ),
        (
            lambda value: value["groups"][0].update(
                {"kind": "CONFLICT", "note": ""}
            ),
            "requires one sparse note",
        ),
    ],
)
def test_compact_response_rejects_invalid_coverage_or_group_shape(mutator, message):
    comparison_input = _comparison_input()
    response = copy.deepcopy(_compact_response())
    mutator(response)

    with pytest.raises(CompareLatencyABError, match=message):
        parse_compact_analysis(
            json.dumps(response),
            comparison_input=comparison_input,
        )


def test_compact_response_rejects_more_groups_than_source_memories():
    comparison_input = _comparison_input()
    response = copy.deepcopy(_compact_response())
    response["groups"].extend(
        [
            {"kind": "DISTINCT", "note": ""},
            {"kind": "DISTINCT", "note": ""},
        ]
    )

    with pytest.raises(CompareLatencyABError, match="Invalid compact group count"):
        parse_compact_analysis(
            json.dumps(response),
            comparison_input=comparison_input,
        )


def test_compact_unresolved_group_requires_required_issue():
    comparison_input = _comparison_input()
    response = _compact_response()
    response["groups"][0] = {
        "kind": "CONFLICT",
        "note": "The policies prescribe incompatible actions.",
    }

    with pytest.raises(CompareLatencyABError, match="requires a REQUIRED issue"):
        parse_compact_analysis(
            json.dumps(response),
            comparison_input=comparison_input,
        )


class _ABProvider:
    def __init__(self) -> None:
        self.identity = ProviderIdentity(
            provider="fake",
            model="fixed",
            reasoning_effort="medium",
        )
        self.last_run = None
        self.operations: list[str] = []

    def complete(self, prompt, *, operation, output_schema=None):
        self.operations.append(operation)
        self.last_run = CompletionRun(identity=self.identity, operation=operation)
        if operation == "compare_contexts":
            response = {
                "overview": "The frames share one claim and retain one unique claim each.",
                "reports": {
                    "both": "Both frames retain the same operational claim.",
                    "differences": "",
                    "reference_only": "The reference has one unique constraint.",
                    "compared_only": "The compared frame has one unique constraint.",
                },
                "relations": [
                    {
                        "relation_key": "g1",
                        "kind": "EQUIVALENT",
                        "status": "RESOLVED",
                        "summary": "The first claims are equivalent.",
                        "reason": "Their operational content is the same.",
                    },
                    {
                        "relation_key": "g2",
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "summary": "The reference constraint is distinct.",
                        "reason": "Only the reference contains it.",
                    },
                    {
                        "relation_key": "g3",
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "summary": "The compared constraint is distinct.",
                        "reason": "Only the compared frame contains it.",
                    },
                ],
                "source_assignments": [
                    {"source_memory_id": "m1_000001", "relation_key": "g1"},
                    {"source_memory_id": "m1_000002", "relation_key": "g2"},
                    {"source_memory_id": "m2_000001", "relation_key": "g1"},
                    {"source_memory_id": "m2_000002", "relation_key": "g3"},
                ],
                "issues": [],
            }
        else:
            response = _compact_response()
        return json.dumps(response)


def test_ab_runner_uses_same_payload_and_scores_decision_agreement():
    provider = _ABProvider()

    record = run_compare_latency_ab(provider, _comparison_input())

    assert record["status"] == "VALID"
    assert provider.operations == ["compare_contexts", "compare_contexts_compact_ab_v1"]
    assert record["corpus"]["baseline_payload_matches_compact_payload"] is True
    calls = {call["condition"]: call for call in record["calls"]}
    assert calls[BASELINE]["contract_valid"] is True
    assert calls[COMPACT]["contract_valid"] is True
    assert calls[COMPACT]["response_chars"] < calls[BASELINE]["response_chars"]
    assert record["agreement"]["source_kind_agreement"] == 1.0
    assert record["agreement"]["source_exact_group_and_kind_agreement"] == 1.0
    assert record["agreement"]["pairwise_same_group"]["f1"] == 1.0


def test_task2_benchmark_input_is_exactly_150_plus_150():
    comparison_input = build_task2_comparison_input(language="en")

    assert tuple(len(frame.memories) for frame in comparison_input.frames) == (150, 150)
    assert sum(len(frame.memories) for frame in comparison_input.frames) == 300


def test_benchmark_ledger_refuses_to_overwrite(tmp_path):
    path = tmp_path / "run.json"
    write_benchmark_ledger(path, {"status": "VALID"})

    with pytest.raises(CompareLatencyABError, match="already exists"):
        write_benchmark_ledger(path, {"status": "VALID"})
