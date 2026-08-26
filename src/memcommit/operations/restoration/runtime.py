"""Shared authority-aware selection of command restoration routes."""

from __future__ import annotations

from memcommit.retained_history.command_history import (
    CommandHistoryError,
    CommandRestoreResult,
    RestoreDirection,
)
from memcommit.operations.update.granted_application import restore_granted_update
from memcommit.store import MemoryStore


def restore_context_command(
    store: MemoryStore,
    direction: RestoreDirection,
) -> CommandRestoreResult:
    """Restore the newest eligible granted or ordinary command unit.

    A staged granted receipt is consulted only when its status can participate
    in the requested direction. An empty authority stack falls back to the
    ordinary global stack; every other authority failure remains fail-closed.
    """

    if direction not in {"undo", "redo"}:
        raise ValueError("Restoration direction must be 'undo' or 'redo'.")
    staged = store.load_staged_update()
    eligible_statuses = (
        {"applied"} if direction == "undo" else {"applied", "undone"}
    )
    if (
        staged is not None
        and staged.status in eligible_statuses
        and staged.granted_target is not None
    ):
        try:
            return restore_granted_update(store, staged, direction)
        except CommandHistoryError as error:
            expected_empty = (
                f"There is no recorded Context command to {direction}."
            )
            if str(error) != expected_empty:
                raise
            # A stale granted receipt can coexist with a newer local command.
            # Fall back only when its authority stack is definitely empty.
    return store.restore_recent_context_command(direction)
