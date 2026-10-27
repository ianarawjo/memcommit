"""Undo the most recent recorded Context command across affected Contexts."""
from __future__ import annotations

import typer

from memcommit.application.capabilities.command_recovery import CommandHistoryError
from memcommit.adapters.console.terminal.components.restoration_receipt import (
    render_command_restore_receipt,
)
from memcommit.application.operations.undo_redo.runtime import execute_undo
from memcommit.persistence.store import ProfileStore


def cmd() -> None:
    """Undo one global checkpoint-producing command unit."""
    store = ProfileStore()
    try:
        result = execute_undo(store)
    except (
        CommandHistoryError,
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(f"Undo error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    render_command_restore_receipt(result)
