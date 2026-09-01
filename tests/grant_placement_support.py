"""Test composition for creating a Grant and then placing it as its receiver."""

from __future__ import annotations

from memcommit.application.operations.profile.config import (
    AuthorityGrant,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    create_authority_grant,
    grant_placement,
    use_profile,
)
from memcommit.application.operations.rename.application import RenameRequest
from memcommit.application.operations.rename.runtime import (
    execute_rename,
    prepare_rename,
)
from memcommit.persistence.store import MemoryStore


def create_authority_grant_with_placement(
    *,
    access_name: str | None = None,
    **grant_options: object,
) -> tuple[ProfileRegistry, AuthorityGrant]:
    """Create authority, then let the active grantee choose its access name."""

    registry, grant = create_authority_grant(**grant_options)
    placement = grant_placement(registry, grant)
    chosen_name = access_name or grant.resource_name
    if placement.access_name == chosen_name:
        return registry, grant
    original_profile = registry.active
    grantee = next(
        profile
        for profile in registry.profiles
        if profile.uid == grant.grantee_profile_uid
    )
    switched = original_profile.uid != grantee.uid
    if switched:
        use_profile(grantee.name)
    try:
        store = MemoryStore(root=profile_store_dir(grantee), create=False)
        plan = prepare_rename(
            store,
            RenameRequest(
                old_locator=placement.access_name,
                new_name=chosen_name,
                current_context_name=store.current_context_name(),
            ),
        )
        execute_rename(store, plan)
    finally:
        if switched:
            use_profile(original_profile.name)
    return load_profile_registry(), grant


__all__ = ["create_authority_grant_with_placement"]
