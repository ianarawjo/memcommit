"""Redo the most recently undone recorded Context command."""
from __future__ import annotations

import typer

from memcommit.command_history import CommandHistoryError
from memcommit.commands.restoration_present import (
    render_command_restore_receipt,
)
from memcommit.granted_update_application import restore_granted_update
from memcommit.store import MemoryStore


def cmd() -> None:
    """Redo one global checkpoint-producing command unit."""
    store = MemoryStore()
    try:
        session = store.load_staged_update()
        if (
            session is not None
            and session.status in {"applied", "undone"}
            and session.granted_target is not None
        ):
            try:
                result = restore_granted_update(store, session, "redo")
            except CommandHistoryError as error:
                if str(error) != "There is no recorded Context command to redo.":
                    raise
                # A stale granted receipt can coexist with a newer local Undo.
                # Fall back only when its authority stack is definitely empty.
                result = store.restore_recent_context_command("redo")
        else:
            result = store.restore_recent_context_command("redo")
    except (
        CommandHistoryError,
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(f"Redo error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    render_command_restore_receipt(result)
