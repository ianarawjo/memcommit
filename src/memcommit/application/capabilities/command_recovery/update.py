"""Recover authority-owned Update publications as one public command."""

from __future__ import annotations

from dataclasses import replace

from memcommit.application.authorization import authorize_context_use
from memcommit.application.context_access.access import (
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.command_recovery.model import (
    CommandRestoreResult,
    CommandHistoryError,
    RestoreDirection,
)
from memcommit.application.context_access import access_context_name
from memcommit.application.operations.profile.model import (
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.update.model import (
    UpdateReceipt,
    required_update_context_uses,
)
from memcommit.application.operations.update.publication import (
    authorize_granted_target_operations,
)
from memcommit.persistence.store import MemoryStore


class UpdateAlreadyRestored(CommandHistoryError):
    """The exact Update is already on the opposite command stack."""


def _public_restore_result(
    result: CommandRestoreResult,
    receipt: UpdateReceipt,
) -> CommandRestoreResult:
    binding = receipt.inputs.granted_target
    if binding is None:
        return result
    changes = tuple(
        replace(
            change,
            context_name=access_context_name(binding, change.context_name),
        )
        for change in result.unit.changes
    )
    return replace(result, unit=replace(result.unit, changes=changes))


def restore_update_command(
    active_store: MemoryStore,
    receipt: UpdateReceipt,
    direction: RestoreDirection,
) -> CommandRestoreResult:
    """Restore the authority command named by a participant Update receipt."""

    if receipt.inputs.granted_target is None:
        raise ValueError("Expected a granted-target Update receipt.")
    binding = receipt.inputs.granted_target
    expected_unit_uid = f"update:{receipt.uid}:{receipt.application.operation_digest}"
    with authority_grant_snapshot_lock() as registry:
        access = revalidate_granted_context_binding(
            binding,
            required_permission="READ",
            registry=registry,
            active_store=active_store,
        )
        authorize_context_use(
            access,
            required_update_context_uses(receipt.plan.operations),
        )
        authorize_granted_target_operations(
            receipt.inputs,
            receipt.plan,
            access,
            registry=registry,
        )
        from memcommit.application.capabilities.command_recovery.stack_reconstruction import (
            build_command_stacks,
        )

        stacks = build_command_stacks(access.store)
        opposite = stacks.redo if direction == "undo" else stacks.undo
        if any(unit.uid == expected_unit_uid for unit in opposite):
            # Historical receipts never toggle status. The authority's recorded
            # command stack alone proves that this direction was already taken.
            raise UpdateAlreadyRestored("Update is already restored in this direction.")
        active_store._assert_profile_write_allowed()
        result = access.store.restore_recent_context_command(
            direction,
            expected_unit_uid=expected_unit_uid,
        )
    return _public_restore_result(result, receipt)


__all__ = ["restore_update_command"]
