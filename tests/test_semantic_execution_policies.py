"""User-facing semantic operations declare one shared execution vocabulary."""

from __future__ import annotations

from memcommit.atomize import _atomize_execution_policy
from memcommit.atomize_grounding_provider import (
    ATOMIZE_GROUNDING_EXECUTION_POLICY,
)
from memcommit.comparison_provider import COMPARISON_EXECUTION_POLICY
from memcommit.find_answer_dialogue import _find_answer_execution_policy
from memcommit.findings import _findings_execution_policy
from memcommit.history_search import HISTORY_SEARCH_EXECUTION_POLICY
from memcommit.meld_provider import MELD_EXECUTION_POLICY
from memcommit.rationale import RATIONALE_EXECUTION_POLICY
from memcommit.search import FIND_EXECUTION_POLICY
from memcommit.selective_curation import (
    CurationBatch,
    CurationItem,
    CriterionFrame,
    SELECTIVE_CURATION_EXECUTION_POLICY,
    build_provider_frame,
    plan_curation_execution,
)
from memcommit.application.semantic_execution import (
    ExecutionMode,
    ExecutionStrategy,
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
)
from memcommit.summarize import SUMMARIZE_EXECUTION_POLICY
from memcommit.operations.translate.runtime import TRANSLATE_EXECUTION_POLICY
from memcommit.update import UPDATE_EXECUTION_POLICY


def test_only_implemented_find_and_translate_policies_advertise_staging():
    assert FIND_EXECUTION_POLICY.strategy is ExecutionStrategy.TOP_K_RERANK
    assert FIND_EXECUTION_POLICY.staged_supported is True
    assert TRANSLATE_EXECUTION_POLICY.strategy is ExecutionStrategy.COVERAGE_MAP
    assert TRANSLATE_EXECUTION_POLICY.staged_supported is True

    guarded = (
        COMPARISON_EXECUTION_POLICY,
        MELD_EXECUTION_POLICY,
        UPDATE_EXECUTION_POLICY,
        _atomize_execution_policy(),
        SUMMARIZE_EXECUTION_POLICY,
        _findings_execution_policy("find_duplicates"),
        _findings_execution_policy("find_ambiguities"),
        _findings_execution_policy("find_conflicts"),
        HISTORY_SEARCH_EXECUTION_POLICY,
        _find_answer_execution_policy(),
        RATIONALE_EXECUTION_POLICY,
        ATOMIZE_GROUNDING_EXECUTION_POLICY,
    )
    assert all(policy.staged_supported is False for policy in guarded)
    assert {
        policy.strategy for policy in guarded
    } == {
        ExecutionStrategy.BLOCK_RELATIONS,
        ExecutionStrategy.MAP_PLUS_GLOBAL,
        ExecutionStrategy.TOP_K_RERANK,
        ExecutionStrategy.HIERARCHICAL_REDUCE,
    }


def test_aggregate_policies_share_provider_capacity_without_count_gates():
    policies = (
        COMPARISON_EXECUTION_POLICY,
        MELD_EXECUTION_POLICY,
        UPDATE_EXECUTION_POLICY,
        _atomize_execution_policy(),
        SUMMARIZE_EXECUTION_POLICY,
        _findings_execution_policy("find_duplicates"),
        _findings_execution_policy("find_ambiguities"),
        _findings_execution_policy("find_conflicts"),
        HISTORY_SEARCH_EXECUTION_POLICY,
        _find_answer_execution_policy(),
        RATIONALE_EXECUTION_POLICY,
        ATOMIZE_GROUNDING_EXECUTION_POLICY,
        FIND_EXECUTION_POLICY,
        TRANSLATE_EXECUTION_POLICY,
        SELECTIVE_CURATION_EXECUTION_POLICY,
    )

    for policy in policies:
        limits = policy.one_shot_limits
        assert limits.max_input_chars == SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT
        assert limits.max_items is None
        assert limits.max_output_items is None
        assert limits.max_relation_edges is None


def test_selective_curation_has_no_fixed_item_count_gate():
    frame = build_provider_frame(
        CurationBatch(
            source_label="source",
            source=tuple(
                CurationItem(f"s{index}", "source content")
                for index in range(501)
            ),
            criteria=CriterionFrame(
                kind="INSTRUCTION",
                label="instruction",
                items=(CurationItem("instruction", "forget this"),),
            ),
        )
    )

    plan = plan_curation_execution(frame)

    assert plan.policy.strategy is ExecutionStrategy.WHOLE_FRAME_ONLY
    assert plan.mode is ExecutionMode.ONE_SHOT
    assert plan.exceeded_axes == ()
