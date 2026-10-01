"""Inspect retained Update publication evidence without mutation."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.application.authorization import authorize_context_use
from memcommit.application.context_access.access import (
    GrantedReadStore,
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.context_scope_loading import load_context_scope
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.update.model import (
    UpdateReceipt,
    inline_update_source,
    required_update_context_uses,
    update_inputs_match,
)
from memcommit.application.operations.update.publication import (
    authorize_granted_target_operations,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class UpdateInspection:
    """Read-only freshness status of one completed Update."""

    status: Literal["current", "stale", "revoked"]
    detail: str = ""


def inspect_update(
    active_store: MemoryStore,
    receipt: UpdateReceipt,
) -> UpdateInspection:
    """Revalidate a retained Update while keeping its diff inspectable."""

    inputs = receipt.inputs
    has_grant = inputs.granted_source is not None or inputs.granted_target is not None
    grant_lock = authority_grant_snapshot_lock() if has_grant else nullcontext(None)
    try:
        with grant_lock as registry:
            inline_source = inline_update_source(inputs)
            if inline_source is not None:
                source = inline_source
            elif inputs.granted_source is None:
                source_store = active_store
                source_name = inputs.source_name
            else:
                source_access = revalidate_granted_context_binding(
                    inputs.granted_source,
                    required_permission="READ",
                    registry=registry,
                    active_store=active_store,
                )
                source_store = GrantedReadStore(source_access, registry=registry)
                source_name = inputs.granted_source.access_name
            if inline_source is None:
                source = (
                    source_store.load_direct(source_name)
                    if inputs.instruction is not None
                    else load_context_scope(
                        source_store,
                        source_name,
                        include_descendants=inputs.source_include_descendants,
                    )
                )

            if inputs.granted_target is None:
                target_store = active_store
                target_name = inputs.target_name
            else:
                target_access = revalidate_granted_context_binding(
                    inputs.granted_target,
                    required_permission="READ",
                    registry=registry,
                    active_store=active_store,
                )
                authorize_context_use(
                    target_access,
                    required_update_context_uses(receipt.plan.operations),
                )
                authorize_granted_target_operations(
                    inputs,
                    receipt.plan,
                    target_access,
                    registry=registry,
                )
                target_store = GrantedReadStore(target_access, registry=registry)
                target_name = inputs.granted_target.access_name
            target = (
                target_store.load_direct(target_name)
                if inputs.instruction is not None
                else load_context_scope(
                    target_store,
                    target_name,
                    include_descendants=inputs.target_include_descendants,
                )
            )
            after_inputs = replace(
                inputs,
                target_digest=receipt.application.target_digest,
                target_contexts=receipt.application.target_contexts,
                target_memory_uid=None,
            )
            fresh = update_inputs_match(
                after_inputs,
                source,
                target,
                granted_source=inputs.granted_source,
                granted_target=inputs.granted_target,
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
