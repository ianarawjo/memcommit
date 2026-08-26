"""Redo the most recently undone recorded Context command."""
from __future__ import annotations

import typer

from memcommit.retained_history.command_history import CommandHistoryError
from memcommit.commands.shared.restoration_present import (
    render_command_restore_receipt,
)
from memcommit.operations.redo.runtime import execute_redo
from memcommit.store import MemoryStore


def cmd() -> None:
    """Redo one global checkpoint-producing command unit."""
    store = MemoryStore()
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
