"""Undo/Redo selection over the local reconstructed command stack."""

from memcommit.persistence.store import MemoryStore
from .model import CommandRestoreResult, RestoreDirection


def restore_context_command(
    store: MemoryStore, direction: RestoreDirection
) -> CommandRestoreResult:
    if direction not in {"undo", "redo"}:
        raise ValueError("Restoration direction must be 'undo' or 'redo'.")
    return store.restore_recent_context_command(direction)
