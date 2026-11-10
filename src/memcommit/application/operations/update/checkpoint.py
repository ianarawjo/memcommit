"""Build Update checkpoint provenance independently of receipt persistence."""

from memcommit.models.context import Context

from .model import (
    UpdateExecutionInputs,
    UpdatePlan,
    UpdateOperation,
)


def build_update_checkpoint(
    execution_inputs: UpdateExecutionInputs,
    plan: UpdatePlan,
    *,
    operation_hash: str,
    owner_uid: str,
    owner_operations: tuple[UpdateOperation, ...],
    updated_contexts: tuple[Context, ...],
) -> dict[str, object]:
    args: dict[str, object] = {
        "update_operation_uid": plan.uid,
        "operation_digest": operation_hash,
        "source_context_uid": execution_inputs.source_uid,
        "source_context_name": execution_inputs.source_name,
        "target_context_uid": execution_inputs.target_uid,
        "target_context_name": execution_inputs.target_name,
        "goal_focus": (
            None
            if execution_inputs.goal_focus is None
            else execution_inputs.goal_focus.receipt_record()
        ),
        "owner_context_uid": owner_uid,
        "operation_memory_uids": [
            operation.memory_uid for operation in owner_operations
        ],
        # Authority history is reconstructed from physical Context records;
        # participant receipts retain the public names separately.
        "command_contexts": [
            {
                "uid": updated_context.uid,
                "name": updated_context.name,
            }
            for updated_context in updated_contexts
        ],
    }
    if execution_inputs.instruction is not None:
        args["instruction_kind"] = (
            "MEMORY" if execution_inputs.source_memory_uid else "TEXT"
        )
        args["source_memory_uid"] = execution_inputs.source_memory_uid
        args["instruction_text"] = execution_inputs.instruction
    return args
