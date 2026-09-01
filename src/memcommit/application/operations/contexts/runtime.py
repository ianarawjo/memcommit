"""Read-only Store and Profile projection for Contexts."""

from __future__ import annotations

from memcommit.core.context_targeting.naming import is_portable_context_name
from memcommit.application.context_access.granted_context_navigation import (
    freeze_granted_context_navigation,
    grant_navigation_capability_text,
)
from memcommit.core.context_targeting.resolution import order_context_names_by_hierarchy
from memcommit.application.operations.contexts.application import (
    ContextCatalogEntry,
    ContextsCatalog,
)
from memcommit.application.operations.profile.config import (
    active_profile_registry_for_store,
)
from memcommit.application.context_access.granted_view import active_grant_placements
from memcommit.persistence.store import MemoryStore


def load_contexts_catalog(store: MemoryStore) -> ContextsCatalog:
    """Freeze the active pointer and its local-plus-Grant public hierarchy."""

    current = store.current_context_name()
    local_name_values = tuple(store.list_context_names())

    granted_navigation = freeze_granted_context_navigation(store)
    registry = active_profile_registry_for_store(store.store_dir)
    profile_names = (
        {profile.uid: profile.name for profile in registry.profiles}
        if registry is not None
        else {}
    )
    active_grants = (
        active_grant_placements(registry=registry)
        if registry is not None
        else ()
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
            (placement, grant)
            for placement, grant in active_grants
            if name == placement.access_name
            or name.startswith(placement.access_name + "/")
        )
        if not candidates:
            continue
        # The nearest lexical Placement selects the effective authority Grant.
        _effective_placement, effective = max(
            candidates,
            key=lambda item: len(item[0].access_name.split("/")),
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
    return ContextsCatalog(
        entries=tuple(entries),
        has_local_contexts=bool(local_name_values),
    )
