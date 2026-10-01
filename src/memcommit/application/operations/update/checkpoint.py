"""Build Update checkpoint provenance independently of receipt persistence."""

from memcommit.application.context_access import (
    GrantedContextBinding,
    authority_context_name,
)
from .model import UpdateContextInputs, UpdatePlan, UpdateOperation, UpdateError


def _physical_name(
    binding: GrantedContextBinding | None,
    public_name: str,
) -> str:
    if binding is None:
        return public_name
    try:
        return authority_context_name(binding, public_name)
    except ValueError as error:
        raise UpdateError(
            "An Update owner is outside its frozen granted namespace."
        ) from error


def build_update_checkpoint(
    inputs: UpdateContextInputs,
    plan: UpdatePlan,
    *,
    operation_hash: str,
    owner_uid: str,
    owner_operations: tuple[UpdateOperation, ...],
    affected_owners,
) -> dict[str, object]:
    target_binding = inputs.granted_target
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
                "uid": owner.owner_context_uid,
                "name": _physical_name(
                    target_binding,
                    owner.owner_context_name,
                ),
            }
            for owner in affected_owners
        ],
    }
    if inputs.instruction is not None:
        args["instruction_kind"] = "MEMORY" if inputs.source_memory_uid else "TEXT"
        args["source_memory_uid"] = inputs.source_memory_uid
        # Private input text stays in the initiating Profile's receipt, not in
        # another owner's checkpoint. The kind still prevents a fictitious --from.
        if target_binding is None:
            args["instruction_text"] = inputs.instruction.text
    if inputs.granted_source is not None:
        args["granted_source"] = inputs.granted_source.to_dict()
    if target_binding is not None:
        args.update(
            {
                "authority_target_context_name": (
                    target_binding.authority_context_name
                ),
                "authority_grant": {
                    "uid": target_binding.grant_uid,
                    "revision": target_binding.grant_revision,
                    "grantee_profile_uid": target_binding.grantee_profile_uid,
                    "access_context": target_binding.access_name,
                },
            }
        )
    return args
