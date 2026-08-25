"""Redo adapter over shared command-restoration mechanics."""

from __future__ import annotations

from memcommit.command_history import CommandRestoreResult
from memcommit.operations.restoration.runtime import restore_context_command
from memcommit.store import MemoryStore


def execute_redo(store: MemoryStore) -> CommandRestoreResult:
    """Redo one globally ordered previously undone command unit."""

    return restore_context_command(store, "redo")
