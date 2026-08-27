"""Redo adapter over shared command-restoration mechanics."""

from __future__ import annotations

from memcommit.retained_history.command_history import CommandRestoreResult
from memcommit.application.operations.restoration.runtime import restore_context_command
from memcommit.persistence.store import MemoryStore


def execute_redo(store: MemoryStore) -> CommandRestoreResult:
    """Redo one globally ordered previously undone command unit."""

    return restore_context_command(store, "redo")
