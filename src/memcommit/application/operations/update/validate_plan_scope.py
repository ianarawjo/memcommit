"""Validate that an Update plan stays within its frozen selection."""

from memcommit.application.operations.update.model import (
    AddOperation,
    UpdateContextInputs,
    UpdateError,
    UpdatePlan,
)


def validate_update_plan_scope(
    inputs: UpdateContextInputs,
    plan: UpdatePlan,
) -> None:
    """Reject another Target or effects outside the selected Memories."""

    if not isinstance(inputs, UpdateContextInputs) or not isinstance(plan, UpdatePlan):
        raise TypeError("Expected frozen Update inputs and an exact plan.")
    if (plan.target_uid, plan.target_name) != (inputs.target_uid, inputs.target_name):
        raise UpdateError(
            "Update plan names a different Target from its frozen inputs."
        )
    if inputs.target_memory_uid is not None and any(
        isinstance(op, AddOperation) or op.memory_uid != inputs.target_memory_uid
        for op in plan.operations
    ):
        raise UpdateError("Update plan exceeds its selected Target Memory.")
    if inputs.source_memory_uid is not None and any(
        ref.memory_uid != inputs.source_memory_uid
        for op in plan.operations
        for ref in op.source_refs
    ):
        raise UpdateError("Update plan cites an unselected Source Memory.")


__all__ = ["validate_update_plan_scope"]
