"""Undo the most recent recorded Context command across affected Contexts."""
from __future__ import annotations

from typing import Annotated

import typer

from memcommit.command_history import CommandHistoryError
from memcommit.commands.restoration_present import (
    render_command_restore_receipt,
)
from memcommit.granted_update_application import restore_granted_update
from memcommit.store import MemoryStore


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
        session = store.load_staged_update()
        if (
            session is not None
            and session.status == "applied"
            and session.granted_target is not None
        ):
            try:
                result = restore_granted_update(store, session, "undo")
            except CommandHistoryError as error:
                if str(error) != "There is no recorded Context command to undo.":
                    raise
                # An old participant receipt must not mask a newer local
                # command. Other authority failures remain fail-closed.
                result = store.restore_recent_context_command("undo")
        else:
            result = store.restore_recent_context_command("undo")
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
