"""Shared source and destination checks for ``mem import``."""

from __future__ import annotations

from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    profile_store_dir,
    validate_profile_name,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    inspect_store,
)
from memcommit.persistence.store import MemoryStore


def source_profile(
    registry: ProfileRegistry,
    name: str,
) -> ProfileEntry:
    """Resolve one visible registered source without changing selection."""

    canonical = validate_profile_name(name)
    profile = registry.by_name(canonical)
    if profile is None:
        raise ProfileError(f"Profile {canonical!r} does not exist.")
    if registry.is_removed(profile):
        raise ProfileError(f"Profile {canonical!r} was removed from direct selection.")
    inspect_store(profile_store_dir(profile))
    return profile


def require_cross_profile_source(
    registry: ProfileRegistry,
    source: ProfileEntry,
) -> None:
    """Keep import-by-value distinct from same-Profile copy operations."""

    if source.uid == registry.active_uid:
        raise ProfileError(
            "Context and Memory import require a different source Profile. "
            "Use branch or ordinary Context commands inside the active Profile."
        )


def require_active_profile_snapshot(
    registry: ProfileRegistry,
    destination: MemoryStore,
) -> None:
    """Reject a destination that no longer matches the frozen registry."""

    expected = profile_store_dir(registry.active).absolute()
    if destination.store_dir.absolute() != expected:
        raise ProfileError(
            "Active Profile changed while import was starting; rerun the command."
        )
