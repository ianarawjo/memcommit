"""Construction of shared Undo/Redo checkpoint receipt metadata."""

from __future__ import annotations

from memcommit.application.capabilities.command_recovery.model import (
    ContextCommandUnit,
    RestoreDirection,
)


def command_restore_metadata(
    *,
    receipt_uid: str,
    direction: RestoreDirection,
    unit: ContextCommandUnit,
) -> dict[str, object]:
    """Return the checkpoint metadata shared by one restoration receipt."""

    return {
        "version": 1,
        "receipt_uid": receipt_uid,
        "direction": direction,
        "source_unit_uid": unit.uid,
        "source_command": unit.command,
        "contexts": [
            {"uid": change.context_uid, "name": change.context_name}
            for change in unit.changes
        ],
    }


__all__ = ["command_restore_metadata"]
