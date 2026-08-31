"""Inspect retained Update publication evidence without mutation."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Literal

from memcommit.application.authorization import authorize_context_use
from memcommit.application.capabilities.authority.context_access import (
    GrantedReadStore,
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.context_scope_loading import load_context_scope
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


__all__ = [
    "UpdateInspection",
    "inspect_update",
]
