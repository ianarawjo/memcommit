"""Undo adapter over shared command-restoration mechanics."""

from __future__ import annotations

from memcommit.application.capabilities.command_recovery import (
    CommandRestoreResult,
    restore_context_command,
)
from memcommit.application.operations.update.granted_target import restore_granted_update
from memcommit.persistence.store import MemoryStore


def execute_undo(store: MemoryStore) -> CommandRestoreResult:
    """Undo one globally ordered checkpoint-producing command unit."""

    return restore_context_command(
        store,
        "undo",
        restore_granted=restore_granted_update,
    )
