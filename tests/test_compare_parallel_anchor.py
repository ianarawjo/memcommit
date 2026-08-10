from __future__ import annotations

import json
from threading import Barrier

import pytest

from memcommit.comparison import ComparisonInput
from memcommit.context import Context, Memory
from memcommit.eval.compare_latency_ab import CompareLatencyABError
from memcommit.eval.compare_parallel_anchor import (
    AnchorBatch,
    AnchorWorkerResult,
    anchor_worker_schema,
    build_anchor_schedule,
    merge_anchor_workers,
    parse_anchor_worker_response,
    run_parallel_anchor_compare,
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


def _worker_result(
    batch: AnchorBatch,
    anchors: tuple[int, ...],
    kinds: tuple[str, ...],
    *,
    valid: bool = True,
) -> AnchorWorkerResult:
    return AnchorWorkerResult(
        batch=batch,
        contract_valid=valid,
        anchors=anchors,
        kinds=kinds,
        failure_category=None if valid else "INVALID_OUTPUT",
        error_type=None,
        validation_error=None if valid else "invalid",
        operation=f"batch-{batch.index}",
        prompt_chars=10,
        prompt_digest="prompt",
        schema_chars=10,
        schema_digest="schema",
        response_chars=10,
        response_digest="response",
        raw_response="{}",
        provider_seconds=1.0,
        validation_seconds=0.0,
        elapsed_seconds=1.0,
        provider_run=None,
    )


def test_anchor_schedule_freezes_six_exact_fifty_position_batches():
    schedule = build_anchor_schedule(300, batch_size=50)

    assert len(schedule) == 6
    assert schedule[0] == AnchorBatch(index=1, start=1, stop=50)
    assert schedule[-1] == AnchorBatch(index=6, start=251, stop=300)
    assert [position for batch in schedule for position in batch.positions] == list(
        range(1, 301)
    )


def test_anchor_worker_schema_is_a_fixed_decision_vector():
    schema = anchor_worker_schema(50)

    assert set(schema["properties"]) == {"p", "k"}
    assert schema["properties"]["p"]["minItems"] == 50
    assert schema["properties"]["p"]["maxItems"] == 50
    assert schema["properties"]["k"]["items"]["enum"] == [
        "_",
        "E",
        "P",
        "S",
        "C",
        "D",
        "U",
    ]


def test_anchor_worker_parser_accepts_prior_batch_anchors():
    anchors, kinds = parse_anchor_worker_response(
        json.dumps({"p": [1, 4], "k": ["_", "D"]}),
        batch=AnchorBatch(index=2, start=3, stop=4),
        source_count=4,
    )

    assert anchors == (1, 4)
    assert kinds == ("_", "D")


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ({"p": [1], "k": ["E"]}, "exactly 2 rows"),
        ({"p": [4, 4], "k": ["_", "D"]}, "invalid canonical anchor"),
        ({"p": [3, 4], "k": ["_", "D"]}, "omitted an anchor kind"),
        ({"p": [1, 4], "k": ["E", "D"]}, "assigned a kind"),
    ],
)
def test_anchor_worker_parser_rejects_invalid_owned_slice(response, message):
    with pytest.raises(CompareLatencyABError, match=message):
        parse_anchor_worker_response(
            json.dumps(response),
            batch=AnchorBatch(index=2, start=3, stop=4),
            source_count=4,
        )


def test_anchor_merge_reconstructs_one_complete_typed_analysis():
    schedule = build_anchor_schedule(4, batch_size=2)
    analysis, minimal_response = merge_anchor_workers(
        (
            _worker_result(schedule[0], (1, 2), ("E", "D")),
            _worker_result(schedule[1], (1, 4), ("_", "D")),
        ),
        comparison_input=_comparison_input(),
    )

    assert json.loads(minimal_response) == {
        "a": [1, 2],
        "b": [1, 3],
        "k": ["E", "D", "D"],
    }
    assert [relation.kind for relation in analysis.relations] == [
        "EQUIVALENT",
        "DISTINCT",
        "DISTINCT",
    ]
    assert sum(len(relation.members) for relation in analysis.relations) == 4


def test_anchor_merge_rejects_a_reference_to_an_absent_anchor():
    schedule = build_anchor_schedule(4, batch_size=2)

    with pytest.raises(CompareLatencyABError, match="absent canonical anchor"):
        merge_anchor_workers(
            (
                _worker_result(schedule[0], (1, 1), ("D", "_")),
                _worker_result(schedule[1], (2, 4), ("_", "D")),
            ),
            comparison_input=_comparison_input(),
        )


class _BarrierProvider:
    def __init__(self, barrier: Barrier, response: dict[str, object]) -> None:
        self.identity = ProviderIdentity(
            provider="fake",
            model="fixed",
            reasoning_effort="medium",
        )
        self.last_run = None
        self._barrier = barrier
        self._response = response
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        del prompt, output_schema
        self.calls += 1
        # A sequential scheduler cannot cross this point, so the test proves
        # the calls overlap without depending on fragile sleep timings.
        self._barrier.wait(timeout=2.0)
        self.last_run = CompletionRun(identity=self.identity, operation=operation)
        return json.dumps(self._response)


def _parallel_providers(*, invalid_second: bool = False):
    barrier = Barrier(2)
    return (
        _BarrierProvider(barrier, {"p": [1, 2], "k": ["E", "D"]}),
        _BarrierProvider(
            barrier,
            (
                {"p": [1], "k": ["_"]}
                if invalid_second
                else {"p": [1, 4], "k": ["_", "D"]}
            ),
        ),
    )


def test_parallel_runner_overlaps_calls_and_merges_after_all_workers():
    providers = _parallel_providers()

    record = run_parallel_anchor_compare(
        providers,
        _comparison_input(),
        batch_size=2,
        max_workers=2,
    )

    assert record["status"] == "VALID"
    assert [provider.calls for provider in providers] == [1, 1]
    assert record["experiment"]["complete_context_per_worker"] is True
    assert record["experiment"]["partial_publication"] is False
    assert record["merge"]["contract_valid"] is True
    assert record["merge"]["normalized_analysis"]["relation_count"] == 3
    assert record["timing"]["actionable_seconds"] is not None


def test_parallel_runner_publishes_no_analysis_when_one_worker_is_invalid():
    providers = _parallel_providers(invalid_second=True)

    record = run_parallel_anchor_compare(
        providers,
        _comparison_input(),
        batch_size=2,
        max_workers=2,
    )

    assert record["status"] == "INCOMPLETE"
    assert [provider.calls for provider in providers] == [1, 1]
    assert record["merge"]["contract_valid"] is False
    assert record["merge"]["normalized_analysis"] is None
    assert "invalid worker call" in record["merge"]["validation_error"]
    assert record["timing"]["actionable_seconds"] is None
