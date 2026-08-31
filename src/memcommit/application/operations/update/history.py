"""Inspect and restore retained Update publication evidence."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.application.authorization import authorize_context_use
from memcommit.application.capabilities.authority.context_access import (
    GrantedReadStore,
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.command_recovery import CommandRestoreResult
from memcommit.application.capabilities.context_scope_loading import load_context_scope
from memcommit.application.context_access import public_context_name
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.update.model import (
    UpdateSession,
    applied_session_matches,
    inline_update_session_source,
    required_update_context_uses,
    session_matches,
)
from memcommit.application.operations.update.publication import (
    authorize_granted_target_operations,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class UpdateInspection:
    """Read-only freshness status of one retained Update session."""

    status: Literal["current", "stale", "revoked"]
    detail: str = ""


def inspect_update(
    active_store: MemoryStore,
    session: UpdateSession,
) -> UpdateInspection:
    """Revalidate a retained Update while keeping its diff inspectable."""

    has_grant = session.granted_source is not None or session.granted_target is not None
    grant_lock = authority_grant_snapshot_lock() if has_grant else nullcontext(None)
    try:
        with grant_lock as registry:
            inline_source = inline_update_session_source(session)
            if inline_source is not None:
                source = inline_source
            elif session.granted_source is None:
                source_store = active_store
                source_name = session.source_name
            else:
                source_access = revalidate_granted_context_binding(
                    session.granted_source,
                    required_permission="READ",
                    registry=registry,
                    active_store=active_store,
                )
                source_store = GrantedReadStore(source_access, registry=registry)
                source_name = session.granted_source.public_name
            if inline_source is None:
                source = load_context_scope(
                    source_store,
                    source_name,
                    include_descendants=session.source_include_descendants,
                )

            if session.granted_target is None:
                target_store = active_store
                target_name = session.target_name
            else:
                target_access = revalidate_granted_context_binding(
                    session.granted_target,
                    required_permission="READ",
                    registry=registry,
                    active_store=active_store,
                )
                authorize_context_use(
                    target_access,
                    required_update_context_uses(session.operations),
                )
                authorize_granted_target_operations(
                    session,
                    target_access,
                    registry=registry,
                )
                target_store = GrantedReadStore(target_access, registry=registry)
                target_name = session.granted_target.public_name
            target = load_context_scope(
                target_store,
                target_name,
                include_descendants=session.target_include_descendants,
            )
            fresh = (
                applied_session_matches(
                    session,
                    source,
                    target,
                    granted_source=session.granted_source,
                    granted_target=session.granted_target,
                )
                if session.status == "applied"
                else session_matches(
                    session,
                    source,
                    target,
                    granted_source=session.granted_source,
                    granted_target=session.granted_target,
                )
            )
            return UpdateInspection("current" if fresh else "stale")
    except ProfileError as error:
        return UpdateInspection("revoked", str(error))
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        return UpdateInspection("stale", str(error))


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


def restore_update_publication(
    active_store: MemoryStore,
    session: UpdateSession,
    direction: Literal["undo", "redo"],
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


__all__ = [
    "UpdateInspection",
    "inspect_update",
    "restore_update_publication",
]
