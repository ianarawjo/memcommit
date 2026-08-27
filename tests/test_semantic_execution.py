"""Operation-neutral semantic budget, partition, and coverage contracts."""

from __future__ import annotations

import pytest

from memcommit.application.semantic_execution import (
    BudgetLimits,
    BudgetVector,
    CoverageError,
    ExecutionMode,
    ExecutionStrategy,
    PartitionError,
    RelationScheduleError,
    SemanticExecutionPolicy,
    decode_exact_source_assignments,
    exact_source_assignment_schema,
    pack_grouped_items,
    plan_semantic_execution,
    build_relation_block_matrix,
    connected_relation_components,
    run_partitioned,
)


def _policy(
    strategy: ExecutionStrategy,
    *,
    staged_supported: bool = True,
) -> SemanticExecutionPolicy:
    return SemanticExecutionPolicy(
        operation="test",
        strategy=strategy,
        one_shot_limits=BudgetLimits(max_input_chars=10, max_items=3),
        staged_supported=staged_supported,
    )


def test_planner_uses_every_declared_budget_axis_and_preserves_strategy():
    policy = _policy(ExecutionStrategy.TOP_K_RERANK)

    one_shot = plan_semantic_execution(
        policy,
        BudgetVector(input_chars=10, item_count=3),
    )
    staged = plan_semantic_execution(
        policy,
        BudgetVector(input_chars=11, item_count=4),
    )

    assert one_shot.mode is ExecutionMode.ONE_SHOT
    assert staged.mode is ExecutionMode.STAGED
    assert staged.exceeded_axes == ("input_chars", "item_count")
    assert staged.policy.strategy is ExecutionStrategy.TOP_K_RERANK


def test_whole_frame_and_unimplemented_staged_policies_reject_overflow():
    whole = SemanticExecutionPolicy(
        operation="whole",
        strategy=ExecutionStrategy.WHOLE_FRAME_ONLY,
        one_shot_limits=BudgetLimits(max_items=2),
        staged_supported=False,
    )
    declared_only = _policy(
        ExecutionStrategy.BLOCK_RELATIONS,
        staged_supported=False,
    )

    assert plan_semantic_execution(
        whole,
        BudgetVector(item_count=3),
    ).mode is ExecutionMode.REJECTED
    assert plan_semantic_execution(
        declared_only,
        BudgetVector(item_count=4),
    ).mode is ExecutionMode.REJECTED


def test_strategy_declaration_does_not_enable_staging_by_default():
    policy = SemanticExecutionPolicy(
        operation="guarded",
        strategy=ExecutionStrategy.TOP_K_RERANK,
        one_shot_limits=BudgetLimits(max_items=1),
    )

    assert plan_semantic_execution(
        policy,
        BudgetVector(item_count=2),
    ).mode is ExecutionMode.REJECTED


def test_partitioner_keeps_fitting_groups_and_splits_only_oversized_group():
    values = (
        ("a", "111"),
        ("a", "22"),
        ("b", "3333"),
        ("c", "444444"),
        ("c", "55"),
    )

    batches = pack_grouped_items(
        values,
        group_key=lambda item: item[0],
        measure=lambda batch: BudgetVector(
            input_chars=sum(len(item[1]) for item in batch),
            item_count=len(batch),
        ),
        limits=BudgetLimits(max_input_chars=6, max_items=2),
    )

    assert batches == (
        (("a", "111"), ("a", "22")),
        (("b", "3333"),),
        (("c", "444444"),),
        (("c", "55"),),
    )


def test_partitioner_never_truncates_one_oversized_item():
    with pytest.raises(PartitionError, match="semantic input item"):
        pack_grouped_items(
            (("a", "oversized"),),
            group_key=lambda item: item[0],
            measure=lambda batch: BudgetVector(
                input_chars=sum(len(item[1]) for item in batch),
            ),
            limits=BudgetLimits(max_input_chars=3),
        )


def test_partitioned_execution_is_exactly_once_and_returns_after_all_batches():
    calls: list[tuple[str, ...]] = []
    progress: list[tuple[str, int, int]] = []

    result = run_partitioned(
        (("a", "b"), ("c",)),
        item_id=lambda item: item,
        execute=lambda batch, _index, _total: (
            calls.append(batch) or "".join(batch)
        ),
        on_progress=lambda value: progress.append(
            (value.phase, value.batch_index, value.batch_count)
        ),
    )

    assert result == ("ab", "c")
    assert calls == [("a", "b"), ("c",)]
    assert progress == [
        ("BATCH", 1, 2),
        ("BATCH", 2, 2),
        ("COMPLETE", 2, 2),
    ]


def test_partitioned_execution_rejects_duplicate_frozen_inputs():
    with pytest.raises(CoverageError, match="unique"):
        run_partitioned(
            (("same",), ("same",)),
            item_id=lambda item: item,
            execute=lambda batch, _index, _total: batch,
        )


def test_exact_source_assignment_schema_freezes_count_and_alias_universe():
    schema = exact_source_assignment_schema(
        ("m1", "m2"),
        relation_key_schema={"type": "string", "maxLength": 20},
    )

    assert schema["minItems"] == 2
    assert schema["maxItems"] == 2
    item = schema["items"]
    assert item["properties"]["source_memory_id"]["enum"] == ["m1", "m2"]
    assert item["properties"]["relation_key"]["maxLength"] == 20
    assert "uniqueItems" not in schema


def test_exact_source_assignment_decoder_requires_every_alias_once():
    expected = ("m1", "m2")

    assert decode_exact_source_assignments(
        [
            {"source_memory_id": "m2", "relation_key": "r2"},
            {"source_memory_id": "m1", "relation_key": "r1"},
        ],
        expected,
    ) == (("m2", "r2"), ("m1", "r1"))

    with pytest.raises(CoverageError, match="repeated"):
        decode_exact_source_assignments(
            [
                {"source_memory_id": "m1", "relation_key": "r1"},
                {"source_memory_id": "m1", "relation_key": "r2"},
            ],
            expected,
        )


def test_relation_block_matrix_exposes_every_batch_coordinate_once():
    blocks = build_relation_block_matrix(
        (("l1", "l2"), ("l3",)),
        (("r1",), ("r2", "r3")),
        left_id=lambda item: item,
        right_id=lambda item: item,
    )

    assert [
        (block.left_batch_index, block.right_batch_index)
        for block in blocks
    ] == [(1, 1), (1, 2), (2, 1), (2, 2)]
    assert sum(len(block.left) * len(block.right) for block in blocks) == 9


def test_relation_components_merge_hyperedges_and_keep_unmatched_singletons():
    components = connected_relation_components(
        ("a", "b", "c", "d", "e"),
        (("a", "b"), ("b", "c"), ("d",)),
    )

    assert components == (("a", "b", "c"), ("d",), ("e",))


def test_relation_components_reject_unknown_observations():
    with pytest.raises(RelationScheduleError, match="unknown"):
        connected_relation_components(("known",), (("known", "unknown"),))
