from __future__ import annotations

import copy
import json

import pytest

from memcommit.comparison import ComparisonInput
from memcommit.context import Context, Memory
from memcommit.eval.compare_latency_ab import BASELINE, COMPACT, CompareLatencyABError
from memcommit.eval.compare_minimal_io import (
    MINIMAL_IO,
    MINIMAL_IO_PAYLOAD_MARKER,
    minimal_content_payload,
    minimal_output_schema,
    parse_minimal_analysis,
    run_minimal_io_compare,
)
from memcommit.provider_types import CompletionRun, ProviderIdentity


def _comparison_input() -> ComparisonInput:
    reference = Context(
        uid="858406ba-5127-4a8e-9c31-f2a21cd970b9",
        name="reference",
    )
    compared = Context(
        uid="c64524c2-a559-4561-b430-a4046fdf8e5c",
        name="compared",
    )
    reference.add(
        Memory(
            uid="acdb0e06-dfcc-4541-bf98-219ce5a17882",
            content="The shared rule applies.",
        )
    )
    reference.add(
        Memory(
            uid="58c7acc0-e05c-47ec-b633-9902bd8641d9",
            content="Reference-only detail.",
        )
    )
    compared.add(
        Memory(
            uid="56e22e8f-ef1f-48f6-aa63-601a2a2c8604",
            content="The shared rule applies.",
        )
    )
    compared.add(
        Memory(
            uid="b097f96d-4a57-49e8-b998-3cc1440e08bd",
            content="Compared-only detail.",
        )
    )
    return ComparisonInput.from_contexts(reference, compared)


def _minimal_response() -> dict[str, object]:
    return {
        "a": [1, 2],
        "b": [1, 3],
        "k": ["E", "D", "D"],
    }


def _normalized_relations() -> list[dict[str, object]]:
    return [
        {
            "kind": "EQUIVALENT",
            "status": "RESOLVED",
            "members": ["m1_000001", "m2_000001"],
        },
        {
            "kind": "DISTINCT",
            "status": "RESOLVED",
            "members": ["m1_000002"],
        },
        {
            "kind": "DISTINCT",
            "status": "RESOLVED",
            "members": ["m2_000002"],
        },
    ]


def _reference_ledger() -> dict[str, object]:
    normalized = {
        "relation_count": 3,
        "issue_count": 0,
        "required_issue_count": 0,
        "kind_counts": {"DISTINCT": 2, "EQUIVALENT": 1},
        "relations": _normalized_relations(),
        "analysis_digest": "unused",
    }
    return {
        "kind": "reference",
        "run_id": "reference-run",
        "status": "VALID",
        "calls": [
            {
                "condition": BASELINE,
                "provider_seconds": 10.0,
                "response_chars": 1000,
                "normalized_analysis": copy.deepcopy(normalized),
            },
            {
                "condition": COMPACT,
                "provider_seconds": 5.0,
                "response_chars": 500,
                "normalized_analysis": copy.deepcopy(normalized),
            },
        ],
    }


def test_minimal_payload_preserves_all_content_and_no_host_metadata():
    comparison_input = _comparison_input()

    payload = minimal_content_payload(comparison_input)

    assert set(payload) == {"a", "b"}
    assert payload == {
        "a": ["The shared rule applies.", "Reference-only detail."],
        "b": ["The shared rule applies.", "Compared-only detail."],
    }
    encoded = json.dumps(payload)
    assert "content_sha256" not in encoded
    assert "memory_id" not in encoded
    assert "position" not in encoded


def test_minimal_schema_has_only_fixed_vectors_and_kind_codes():
    schema = minimal_output_schema(2, 3)

    assert set(schema["properties"]) == {"a", "b", "k"}
    assert schema["properties"]["a"]["minItems"] == 2
    assert schema["properties"]["a"]["maxItems"] == 2
    assert schema["properties"]["b"]["minItems"] == 3
    assert schema["properties"]["b"]["maxItems"] == 3
    assert schema["properties"]["k"]["items"]["enum"] == [
        "E",
        "P",
        "S",
        "C",
        "D",
        "U",
    ]


def test_minimal_response_reconstructs_current_typed_analysis():
    analysis = parse_minimal_analysis(
        json.dumps(_minimal_response()),
        comparison_input=_comparison_input(),
    )

    assert [relation.kind for relation in analysis.relations] == [
        "EQUIVALENT",
        "DISTINCT",
        "DISTINCT",
    ]
    assert sum(len(relation.members) for relation in analysis.relations) == 4
    assert analysis.issues == ()


def test_minimal_unresolved_group_gets_host_owned_required_review_marker():
    response = _minimal_response()
    response["k"][0] = "C"

    analysis = parse_minimal_analysis(
        json.dumps(response),
        comparison_input=_comparison_input(),
    )

    assert analysis.relations[0].kind == "CONFLICT"
    assert analysis.relations[0].status == "UNRESOLVED"
    assert len(analysis.issues) == 1
    assert analysis.issues[0].priority == "REQUIRED"
    assert "intentionally deferred" in analysis.relations[0].reason


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda value: value["a"].pop(), "exactly 2 assignments"),
        (lambda value: value["k"].append("D"), "Every minimal relation kind"),
        (lambda value: value["k"].__setitem__(0, "D"), "exactly one source side"),
        (
            lambda value: value["k"].__setitem__(1, "E"),
            "cross-source group must contain both",
        ),
    ],
)
def test_minimal_parser_rejects_invalid_vector_or_side_shape(mutator, message):
    response = _minimal_response()
    mutator(response)

    with pytest.raises(CompareLatencyABError, match=message):
        parse_minimal_analysis(
            json.dumps(response),
            comparison_input=_comparison_input(),
        )


class _MinimalProvider:
    def __init__(self) -> None:
        self.identity = ProviderIdentity(
            provider="fake",
            model="fixed",
            reasoning_effort="medium",
        )
        self.last_run = None
        self.prompt = ""
        self.schema = None

    def complete(self, prompt, *, operation, output_schema=None):
        self.prompt = prompt
        self.schema = output_schema
        self.last_run = CompletionRun(identity=self.identity, operation=operation)
        return json.dumps(_minimal_response())


def test_minimal_runner_retains_evidence_and_compares_both_reference_calls():
    provider = _MinimalProvider()

    record = run_minimal_io_compare(
        provider,
        _comparison_input(),
        reference_ledger=_reference_ledger(),
        reference_ledger_digest="reference-digest",
    )

    assert record["status"] == "VALID"
    assert record["call"]["condition"] == MINIMAL_IO
    assert record["call"]["contract_valid"] is True
    assert record["corpus"]["all_content_preserved_in_order"] is True
    assert set(record["comparisons"]) == {BASELINE, COMPACT}
    assert record["comparisons"][BASELINE]["source_kind_agreement"] == 1.0
    assert record["comparisons"][COMPACT]["pairwise_same_group"]["f1"] == 1.0
    payload = json.loads(provider.prompt.split(MINIMAL_IO_PAYLOAD_MARKER, 1)[1])
    assert payload == minimal_content_payload(_comparison_input())
