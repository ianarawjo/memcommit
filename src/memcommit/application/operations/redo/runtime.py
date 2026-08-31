"""Redo adapter over shared command-restoration mechanics."""

from __future__ import annotations

from memcommit.application.capabilities.command_recovery import (
    CommandRestoreResult,
    restore_context_command,
)
from memcommit.application.capabilities.command_recovery.update import (
    restore_update_command,
)
from memcommit.persistence.store import MemoryStore


def execute_redo(store: MemoryStore) -> CommandRestoreResult:
    """Redo one globally ordered previously undone command unit."""

    return restore_context_command(
        store,
        "redo",
        restore_granted=restore_update_command,
    )
