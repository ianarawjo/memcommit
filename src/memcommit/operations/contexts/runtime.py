"""Read-only Store and Profile projection for Contexts."""

from __future__ import annotations

from memcommit.context_targeting.naming import is_portable_context_name
from memcommit.context_targeting.catalog import (
    freeze_granted_context_navigation,
    grant_navigation_capability_text,
)
from memcommit.context_targeting.resolution import order_context_names_by_hierarchy
from memcommit.operations.contexts.application import (
    ContextCatalogEntry,
    ContextsCatalog,
)
from memcommit.operations.profile.config import load_profile_registry
from memcommit.persistence.store import MemoryStore


def load_contexts_catalog(store: MemoryStore) -> ContextsCatalog:
    """Freeze the active pointer and its local-plus-Grant public hierarchy."""

    # Keep the established empty-local behavior: Contexts is an orientation
    # view of this Store, not a Profile-wide Grant browser without a local root.
    current = store.current_context_name()
    local_name_values = tuple(store.list_context_names())
    if not local_name_values:
        return ContextsCatalog(entries=(), has_local_contexts=False)

    granted_navigation = freeze_granted_context_navigation(store)
    registry = load_profile_registry()
    profile_names = {profile.uid: profile.name for profile in registry.profiles}
    active_grants = tuple(
        grant
        for grant in registry.grants
        if grant.grantee_profile_uid == registry.active.uid
    )
    local_names = frozenset(local_name_values)
    public_names = order_context_names_by_hierarchy(
        (
            *local_name_values,
            *(
                name
                for name in granted_navigation.names
                if name not in local_names
            ),
        )
    )

    entries: list[ContextCatalogEntry] = []
    for name in public_names:
        if name in local_names:
            entries.append(
                ContextCatalogEntry(
                    name=name,
                    current=name == current,
                    ownership="OWNED",
                    portable_name=is_portable_context_name(name),
                )
            )
            continue

        candidates = tuple(
            grant
            for grant in active_grants
            if name == grant.public_name or name.startswith(grant.public_name + "/")
        )
        if not candidates:
            continue
        # The nearest lexical Grant is the effective authority. Attachment
        # metadata never becomes a hierarchy edge.
        effective = max(
            candidates,
            key=lambda grant: len(grant.public_name.split("/")),
        )
        entries.append(
            ContextCatalogEntry(
                name=name,
                current=name == current,
                ownership="GRANT",
                portable_name=is_portable_context_name(name),
                capabilities=grant_navigation_capability_text(
                    effective.permissions
                ),
                authority_profile=profile_names[
                    effective.authority_profile_uid
                ],
            )
        )
    return ContextsCatalog(entries=tuple(entries), has_local_contexts=True)
