"""Recover authority-owned Update publications as one public command."""

from __future__ import annotations

from dataclasses import replace

from memcommit.application.authorization import authorize_context_use
from memcommit.application.capabilities.authority.context_access import (
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.command_recovery.model import (
    CommandRestoreResult,
    RestoreDirection,
)
from memcommit.application.context_access import public_context_name
from memcommit.application.operations.profile.model import (
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.semantic_updates.foundation.update.model import (
    UpdateSession,
    required_update_context_uses,
)
from memcommit.application.operations.semantic_updates.foundation.update.publication import (
    authorize_granted_target_operations,
)
from memcommit.persistence.store import MemoryStore


def _public_restore_result(
    result: CommandRestoreResult,
    session: UpdateSession,
) -> CommandRestoreResult:
    binding = session.granted_target
    if binding is None:
        return result
    changes = tuple(
        replace(
            change,
            context_name=public_context_name(binding, change.context_name),
        )
        for change in result.unit.changes
    )
    return replace(result, unit=replace(result.unit, changes=changes))


def restore_update_command(
    active_store: MemoryStore,
    session: UpdateSession,
    direction: RestoreDirection,
) -> CommandRestoreResult:
    """Restore the authority command named by a participant Update receipt."""

    restorable_statuses = {"applied"} if direction == "undo" else {
        "applied",
        "undone",
    }
    if (
        session.status not in restorable_statuses
        or session.granted_target is None
        or session.application is None
    ):
        raise ValueError("Expected one restorable authority Update session.")
    binding = session.granted_target
    expected_unit_uid = f"update:{session.uid}:{session.application.operation_digest}"
    with authority_grant_snapshot_lock() as registry:
        access = revalidate_granted_context_binding(
            binding,
            required_permission="READ",
            registry=registry,
            active_store=active_store,
        )
        authorize_context_use(
            access,
            required_update_context_uses(session.operations),
        )
        authorize_granted_target_operations(
            session,
            access,
            registry=registry,
        )
        active_store._assert_profile_write_allowed()
        result = access.store.restore_recent_context_command(
            direction,
            expected_unit_uid=expected_unit_uid,
        )
        restored_session = (
            session.with_restored_application(applied=False)
            if direction == "undo"
            else session.with_restored_application(applied=True)
            if session.status == "undone"
            else session
        )
        if restored_session != session:
            try:
                active_store.save_staged_update(
                    restored_session,
                    expected_current=session,
                )
            except Exception:
                # Authority history and the participant receipt form one
                # public command. Reverse one if publishing the other fails.
                access.store.restore_recent_context_command(
                    "redo" if direction == "undo" else "undo",
                    expected_unit_uid=expected_unit_uid,
                )
                raise
    return _public_restore_result(result, session)


__all__ = ["restore_update_command"]
