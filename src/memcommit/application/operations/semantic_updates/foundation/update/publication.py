"""Authorize and coordinate publication of one exact Update session."""

from __future__ import annotations

from contextlib import nullcontext

from memcommit.application.authorization import ContextUse, authorize_context_use
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    revalidate_granted_context_binding,
)
from memcommit.application.operations.profiles.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
    resolve_granted_context_view,
)
from memcommit.application.operations.semantic_updates.foundation.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdateError,
    UpdateOperation,
    UpdateSession,
    required_update_context_uses,
)
from memcommit.persistence.operations.update.publication_repository import (
    publish_update_transaction,
)
from memcommit.persistence.store import MemoryStore


def _operation_use(operation: UpdateOperation) -> ContextUse:
    if isinstance(operation, AddOperation):
        return ContextUse.CREATE
    if isinstance(operation, EditOperation):
        return ContextUse.UPDATE
    if isinstance(operation, RemoveOperation):
        return ContextUse.DELETE
    raise TypeError("Unsupported Update operation.")


def authorize_granted_target_operations(
    session: UpdateSession,
    access: ContextAccess,
    *,
    registry,
) -> None:
    """Authorize every public owner against the same frozen Target Grant."""

    binding = session.granted_target
    if binding is None or access.view is None:
        raise UpdateError("Expected a granted Update Target.")
    uses_by_owner: dict[str, set[ContextUse]] = {}
    for operation in session.operations:
        uses_by_owner.setdefault(operation.owner_context_name, set()).add(
            _operation_use(operation)
        )
    for public_name, uses in uses_by_owner.items():
        view = resolve_granted_context_view(
            public_name,
            attachment_name=binding.attachment_context_name,
            required_permission="READ",
            registry=registry,
        )
        owner_access = ContextAccess(
            store=access.store,
            context_name=view.authority_context_name,
            display_name=public_name,
            attachment_name=binding.attachment_context_name,
            permission="READ",
            view=view,
        )
        authorize_context_use(
            owner_access,
            frozenset(uses) | {ContextUse.READ},
        )
        if (
            view.grant.uid != binding.grant_uid
            or view.grant.revision != binding.grant_revision
            or view.authority.uid != binding.authority_profile_uid
            or view.grantee.uid != binding.grantee_profile_uid
        ):
            raise ProfileError(
                "An Update owner is controlled by a different or changed Grant."
            )


def apply_staged_update(
    active_store: MemoryStore,
    session: UpdateSession,
) -> UpdateSession:
    """Authorize an exact staged Update and publish it transactionally."""

    if not isinstance(session, UpdateSession) or session.status != "staged":
        raise ValueError("Expected one staged UpdateSession.")
    source_binding = session.granted_source
    target_binding = session.granted_target
    grant_lock = (
        authority_grant_snapshot_lock()
        if source_binding is not None or target_binding is not None
        else nullcontext(None)
    )
    with grant_lock as registry:
        source_access = (
            None
            if source_binding is None
            else revalidate_granted_context_binding(
                source_binding,
                required_permission="READ",
                registry=registry,
                active_store=active_store,
            )
        )
        if source_access is not None:
            authorize_context_use(source_access, ContextUse.READ)
        target_access = (
            None
            if target_binding is None
            else revalidate_granted_context_binding(
                target_binding,
                required_permission="READ",
                registry=registry,
                active_store=active_store,
            )
        )
        if target_access is not None:
            authorize_context_use(
                target_access,
                required_update_context_uses(session.operations),
            )
            authorize_granted_target_operations(
                session,
                target_access,
                registry=registry,
            )
        return publish_update_transaction(
            active_store,
            session,
            registry=registry,
            source_access=source_access,
            target_access=target_access,
        )


__all__ = ["apply_staged_update", "authorize_granted_target_operations"]
