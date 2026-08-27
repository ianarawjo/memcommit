from __future__ import annotations

import copy
import json
import time

import pytest

from memcommit.application.operations.compare.ledger.model import ComparisonInput
from memcommit.core.context import Context, Memory
from memcommit.providers.types import CompletionRun, ProviderIdentity
from memcommit.study_scenarios.legacy.prewarm.compare_compact import (
    COMPACT_CONDITION,
    CompactCompareError,
    compact_output_schema,
    parse_compact_analysis,
    run_compact_compare,
)


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
    analysis = parse_compact_analysis(
        json.dumps(_compact_response()),
        comparison_input=_comparison_input(),
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
            lambda value: value["groups"].append({"kind": "DISTINCT", "note": ""}),
            "Every compact group must be used",
        ),
        (
            lambda value: value["groups"][0].update({"kind": "DISTINCT"}),
            "exactly one source side",
        ),
        (
            lambda value: value["groups"][0].update({"kind": "CONFLICT", "note": ""}),
            "requires one sparse note",
        ),
    ],
)
def test_compact_response_rejects_invalid_coverage_or_group_shape(mutator, message):
    response = copy.deepcopy(_compact_response())
    mutator(response)

    with pytest.raises(CompactCompareError, match=message):
        parse_compact_analysis(
            json.dumps(response),
            comparison_input=_comparison_input(),
        )


def test_compact_response_rejects_more_groups_than_source_memories():
    response = copy.deepcopy(_compact_response())
    response["groups"].extend(
        [
            {"kind": "DISTINCT", "note": ""},
            {"kind": "DISTINCT", "note": ""},
        ]
    )

    with pytest.raises(CompactCompareError, match="Invalid compact group count"):
        parse_compact_analysis(
            json.dumps(response),
            comparison_input=_comparison_input(),
        )


def test_compact_unresolved_group_requires_required_issue():
    response = _compact_response()
    response["groups"][0] = {
        "kind": "CONFLICT",
        "note": "The policies prescribe incompatible actions.",
    }

    with pytest.raises(CompactCompareError, match="requires a REQUIRED issue"):
        parse_compact_analysis(
            json.dumps(response),
            comparison_input=_comparison_input(),
        )


class _CompactProvider:
    def __init__(self, response: dict[str, object]) -> None:
        self.identity = ProviderIdentity(
            provider="fake",
            model="fixed",
            reasoning_effort="medium",
        )
        self.last_run = None
        self.operations: list[str] = []
        self.response = response

    def complete(self, prompt, *, operation, output_schema=None):
        self.operations.append(operation)
        self.last_run = CompletionRun(identity=self.identity, operation=operation)
        return json.dumps(self.response)


def test_compact_runner_captures_one_valid_study_prewarm_call():
    provider = _CompactProvider(_compact_response())

    result = run_compact_compare(
        provider,
        _comparison_input(),
        clock=time.monotonic,
    )

    assert result.analysis is not None
    assert provider.operations == ["compare_contexts_compact_ab_v1"]
    assert result.evidence["condition"] == COMPACT_CONDITION
    assert result.evidence["contract_valid"] is True
    assert result.evidence["validation_error"] is None


def test_compact_runner_returns_invalid_evidence_for_graph_fallback():
    response = _compact_response()
    response["groups"][0] = {
        "kind": "CONFLICT",
        "note": "The policies prescribe incompatible actions.",
    }
    provider = _CompactProvider(response)

    result = run_compact_compare(
        provider,
        _comparison_input(),
        clock=time.monotonic,
    )

    assert result.analysis is None
    assert result.evidence["contract_valid"] is False
    assert "requires a REQUIRED issue" in str(result.evidence["validation_error"])
