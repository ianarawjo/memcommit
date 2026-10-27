"""Redo the most recently undone recorded Context command."""
from __future__ import annotations

import typer

from memcommit.application.capabilities.command_recovery import CommandHistoryError
from memcommit.adapters.console.terminal.components.restoration_receipt import (
    render_command_restore_receipt,
)
from memcommit.application.operations.undo_redo.runtime import execute_redo
from memcommit.persistence.store import ProfileStore


def cmd() -> None:
    """Redo one global checkpoint-producing command unit."""
    store = ProfileStore()
    try:
        result = execute_redo(store)
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
