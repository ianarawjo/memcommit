"""Undo the most recent recorded Context command across affected Contexts."""
from __future__ import annotations

from typing import Annotated

import typer

from memcommit.retained_history.command_history import CommandHistoryError
from memcommit.commands.shared.restoration_present import (
    render_command_restore_receipt,
)
from memcommit.application.operations.undo.runtime import execute_undo
from memcommit.persistence.store import MemoryStore


def cmd(
    keep: Annotated[
        bool,
        typer.Option(
            "--keep",
            "-k",
            help=(
                "Compatibility option; command-unit Undo always preserves "
                "checkpoint history"
            ),
        ),
    ] = False,
) -> None:
    """Undo one global checkpoint-producing command unit."""
    del keep
    store = MemoryStore()
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
