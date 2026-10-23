"""Build Update checkpoint provenance independently of receipt persistence."""

from .model import (
    UpdateContextInputs,
    UpdatePlan,
    UpdateOperation,
    UpdatedContext,
)


def build_update_checkpoint(
    inputs: UpdateContextInputs,
    plan: UpdatePlan,
    *,
    operation_hash: str,
    owner_uid: str,
    owner_operations: tuple[UpdateOperation, ...],
    updated_contexts: tuple[UpdatedContext, ...],
) -> dict[str, object]:
    args: dict[str, object] = {
        "update_operation_uid": plan.uid,
        "operation_digest": operation_hash,
        "source_context_uid": inputs.source_uid,
        "source_context_name": inputs.source_name,
        "target_context_uid": inputs.target_uid,
        "target_context_name": inputs.target_name,
        "goal_focus": (
            None if inputs.goal_focus is None else inputs.goal_focus.receipt_record()
        ),
        "owner_context_uid": owner_uid,
        "operation_memory_uids": [
            operation.memory_uid for operation in owner_operations
        ],
        # Authority history is reconstructed from physical Context records;
        # participant receipts retain the public names separately.
        "command_contexts": [
            {
                "uid": updated_context.context_uid,
                "name": updated_context.context_name,
            }
            for updated_context in updated_contexts
        ],
    }
    if inputs.instruction is not None:
        args["instruction_kind"] = "MEMORY" if inputs.source_memory_uid else "TEXT"
        args["source_memory_uid"] = inputs.source_memory_uid
        args["instruction_text"] = inputs.instruction.text
    return args
