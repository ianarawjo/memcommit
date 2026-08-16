"""Frozen Profile/Store orientation for operation-neutral launchers."""

from __future__ import annotations

from pathlib import Path

import memcommit.store as store_module
from memcommit.interfaces.tui.components.operation_launcher import LauncherOrientation
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.store import MemoryStore


def operation_launcher_orientation(
    store: MemoryStore | None = None,
) -> LauncherOrientation:
    """Describe the frozen Store without coupling a launcher to Ground.

    ``memcommit.store`` freezes its root at import time. Another process may
    change the registry's active profile while a launcher is open, so matching
    the frozen root is authoritative and the registry's active UID is not.
    """

    frozen_root = (
        store.store_dir if store is not None else Path(store_module.STORE_DIR)
    )
    profile_name = "(unregistered)"
    try:
        registry = load_profile_registry()
    except ProfileConfigError:
        profile_name = "(registry unavailable)"
    else:
        matches = tuple(
            profile.name
            for profile in registry.profiles
            if profile_store_dir(profile) == frozen_root
        )
        if len(matches) == 1:
            profile_name = matches[0]
    return LauncherOrientation(
        rows=(
            ("PROFILE", profile_name),
            ("STORE", str(frozen_root)),
        )
    )


__all__ = ["operation_launcher_orientation"]
