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
    build_provider_frame,
    plan_curation_execution,
)
from memcommit.semantic_execution import ExecutionMode, ExecutionStrategy
from memcommit.summarize import SUMMARIZE_EXECUTION_POLICY
from memcommit.translate import TRANSLATE_EXECUTION_POLICY
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


def test_update_keeps_character_and_operation_budgets_independent():
    limits = UPDATE_EXECUTION_POLICY.one_shot_limits

    assert limits.max_input_chars == 200_000
    assert limits.max_output_items == 200


def test_selective_curation_is_explicitly_whole_frame_only():
    frame = build_provider_frame(
        CurationBatch(
            source_label="source",
            source=tuple(
                CurationItem(f"s{index}", "source content")
                for index in range(500)
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
    assert plan.mode is ExecutionMode.REJECTED
    assert plan.exceeded_axes == ("item_count",)
