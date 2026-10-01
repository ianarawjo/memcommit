"""Shared Undo/Redo selection over reconstructed command stacks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from memcommit.application.capabilities.command_recovery.model import (
    CommandHistoryError,
    CommandRestoreResult,
    RestoreDirection,
)
from memcommit.persistence.store import MemoryStore


GrantedCommandRestorer = Callable[
    [MemoryStore, Any, RestoreDirection],
    CommandRestoreResult,
]


def restore_context_command(
    store: MemoryStore,
    direction: RestoreDirection,
    *,
    restore_granted: GrantedCommandRestorer,
) -> CommandRestoreResult:
    """Restore the newest eligible granted or ordinary command unit.

    A completed granted receipt is consulted only when authority history permits
    the requested direction. An empty authority stack falls back to the
    ordinary global stack; every other authority failure remains fail-closed.
    """

    if direction not in {"undo", "redo"}:
        raise ValueError("Restoration direction must be 'undo' or 'redo'.")
    from memcommit.persistence.operations.update.receipt_repository import (
        UpdateReceiptRepository,
    )

    receipts = UpdateReceiptRepository(store).list()
    from memcommit.application.capabilities.command_recovery.update import (
        UpdateAlreadyRestored,
    )

    for receipt in receipts:
        if receipt.inputs.granted_target is None or not receipt.plan.operations:
            continue
        try:
            return restore_granted(store, receipt, direction)
        except UpdateAlreadyRestored:
            continue
        except CommandHistoryError as error:
            expected_empty = f"There is no recorded Context command to {direction}."
            if str(error) != expected_empty:
                raise
            # Only an empty stack or an explicit opposite-stack match permits
            # fallback. A newer authority command must never be substituted.
    return store.restore_recent_context_command(direction)
