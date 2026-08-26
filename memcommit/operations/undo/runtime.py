"""Undo adapter over shared command-restoration mechanics."""

from __future__ import annotations

from memcommit.retained_history.command_history import CommandRestoreResult
from memcommit.operations.restoration.runtime import restore_context_command
from memcommit.store import MemoryStore


def execute_undo(store: MemoryStore) -> CommandRestoreResult:
    """Undo one globally ordered checkpoint-producing command unit."""

    return restore_context_command(store, "undo")
