"""Pure selection of one-shot, staged, or rejected semantic execution."""

from __future__ import annotations

from memcommit.semantic_execution.model import (
    BudgetVector,
    ExecutionMode,
    ExecutionPlan,
    ExecutionStrategy,
    SemanticExecutionPolicy,
)


def plan_semantic_execution(
    policy: SemanticExecutionPolicy,
    workload: BudgetVector,
) -> ExecutionPlan:
    """Choose execution shape without opening a provider or altering the frame."""

    if not isinstance(policy, SemanticExecutionPolicy):
        raise TypeError("Expected a semantic execution policy.")
    if not isinstance(workload, BudgetVector):
        raise TypeError("Expected a semantic workload budget.")
    exceeded = policy.one_shot_limits.exceeded_axes(workload)
    if not exceeded:
        mode = ExecutionMode.ONE_SHOT
    elif (
        policy.strategy is ExecutionStrategy.WHOLE_FRAME_ONLY
        or not policy.staged_supported
    ):
        mode = ExecutionMode.REJECTED
    else:
        mode = ExecutionMode.STAGED
    return ExecutionPlan(
        policy=policy,
        workload=workload,
        mode=mode,
        exceeded_axes=exceeded,
    )
