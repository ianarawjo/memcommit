import uuid

import pytest

from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonInput,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
)
from memcommit.context import Context
import memcommit.ops as ops
from memcommit.eval.compare_prewarm_projection import (
    build_deletion_input,
    compare_relation_ledgers,
    measure_exact_warm_cache,
    project_primary_relations,
)


def _input() -> ComparisonInput:
    left = Context(uid=str(uuid.uuid4()), name="left")
    right = Context(uid=str(uuid.uuid4()), name="right")
    ops.add(left, "left one")
    ops.add(left, "left two")
    ops.add(right, "right one")
    ops.add(right, "right two")
    return ComparisonInput.from_contexts(left, right)


def _relation(
    comparison_input: ComparisonInput,
    kind: str,
    members: tuple[tuple[int, int], ...],
) -> ComparisonRelation:
    status = "UNRESOLVED" if kind in {"CONFLICT", "UNCLEAR"} else "RESOLVED"
    return ComparisonRelation.from_dict(
        {
            "uid": str(uuid.uuid4()),
            "kind": kind,
            "status": status,
            "members": [
                ComparisonMember(
                    frame_uid=comparison_input.frames[frame_index].uid,
                    memory_uid=comparison_input.frames[frame_index].memories[
                        memory_index
                    ].uid,
                ).to_dict()
                for frame_index, memory_index in members
            ],
            "summary": f"{kind} summary",
            "reason": f"{kind} reason",
        }
    )


def _analysis(comparison_input: ComparisonInput) -> ComparisonAnalysis:
    return ComparisonAnalysis.create(
        comparison_input,
        overview="Complete small comparison.",
        reports=ComparisonReports(
            both="Both report.",
            differences="Differences report.",
            reference_only="",
            compared_only="",
        ),
        relations=(
            _relation(comparison_input, "SCOPED", ((0, 1), (1, 0))),
            _relation(comparison_input, "EQUIVALENT", ((0, 0), (1, 1))),
        ),
        issues=(),
    )


def test_deletion_projection_reports_invalid_remnant_and_complete_coverage():
    full_input = _input()
    surviving_input = build_deletion_input(full_input)

    projected = project_primary_relations(
        _analysis(full_input),
        surviving_input,
        full_input,
    )

    assert [len(frame.memories) for frame in surviving_input.frames] == [1, 2]
    assert projected["source_count"] == 3
    assert projected["cut_relation_count"] == 1
    assert projected["invalid_side_shape_count"] == 1
    assert projected["raw_projection_structurally_valid"] is False
    assert projected["coverage"] == {
        "expected": 3,
        "observed_unique": 3,
        "duplicate_count": 0,
        "missing": [],
        "unknown": [],
    }
    assert projected["shape_repaired_relations"] == [
        {"kind": "DISTINCT", "members": ["b001"]},
        {"kind": "EQUIVALENT", "members": ["a001", "b002"]},
    ]


def test_shape_repaired_projection_can_match_fresh_relation_ledger():
    full_input = _input()
    projected = project_primary_relations(
        _analysis(full_input),
        build_deletion_input(full_input),
        full_input,
    )
    fresh = [
        {"kind": "DISTINCT", "members": ["b001"]},
        {"kind": "EQUIVALENT", "members": ["a001", "b002"]},
    ]

    agreement = compare_relation_ledgers(
        projected["shape_repaired_relations"],
        fresh,
    )

    assert agreement["source_kind_agreement"] == 1.0
    assert agreement["exact_source_group_and_kind_agreement"] == 1.0
    assert agreement["pairwise_same_group"]["f1"] == 1.0


def test_relation_agreement_rejects_mismatched_source_coverage():
    with pytest.raises(Exception, match="same sources"):
        compare_relation_ledgers(
            [{"kind": "DISTINCT", "members": ["a001"]}],
            [{"kind": "DISTINCT", "members": ["b001"]}],
        )


def test_exact_warm_cache_never_calls_analyzer():
    full_input = _input()

    result = measure_exact_warm_cache(
        _analysis(full_input),
        full_input,
        repetitions=3,
    )

    assert result["provider_calls"] == 0
    assert result["reused"] is True
    assert result["timing"]["repetitions"] == 3
    assert result["timing"]["maximum_seconds"] >= 0
