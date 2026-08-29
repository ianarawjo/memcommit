"""Frozen Profile/Store orientation for operation-neutral launchers."""

from __future__ import annotations

from pathlib import Path

import memcommit.persistence.store as store_module
from memcommit.adapters.console.terminal.components.operation_launcher import LauncherOrientation
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionPickerLocation,
)
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.persistence.store import MemoryStore


def operation_launcher_orientation(
    store: MemoryStore | None = None,
) -> LauncherOrientation:
    """Describe the frozen Store without coupling a launcher to Ground.

    ``memcommit.persistence.store`` freezes its root at import time. Another process may
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


def session_picker_location(
    store: MemoryStore | None = None,
) -> SessionPickerLocation:
    """Project the shared launcher orientation into the session adapter."""

    orientation = operation_launcher_orientation(store)
    rows = dict(orientation.rows)
    return SessionPickerLocation(
        profile_name=rows["PROFILE"],
        store_path=rows["STORE"],
    )


__all__ = ["operation_launcher_orientation", "session_picker_location"]
