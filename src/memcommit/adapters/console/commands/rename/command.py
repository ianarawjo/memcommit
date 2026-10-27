"""Rename one local Context namespace."""

from __future__ import annotations

from typing import Annotated

import typer

from memcommit.application.operations.rename.application import RenameRequest
from memcommit.application.operations.rename.runtime import (
    execute_rename,
    prepare_rename,
)
from memcommit.persistence.store import ProfileStore


def cmd(
    old: Annotated[
        str,
        typer.Argument(
            metavar="OLD_CONTEXT_NAME",
            help=(
                "Existing local Context name; local "
                "Contexts also accept '.', '..', './child', or a UID selector"
            ),
        ),
    ],
    new: Annotated[
        str,
        typer.Argument(
            metavar="NEW_CONTEXT_NAME",
            help=(
                "New portable canonical Context name; lexical relative selectors "
                "are not accepted"
            ),
        ),
    ],
) -> None:
    """Rename a local Context namespace."""
    store = ProfileStore()
    current = store.current_context_name()
    try:
        plan = prepare_rename(
            store,
            RenameRequest(
                old_locator=old,
                new_name=new,
                current_context_name=current,
            ),
        )
    except (
        FileExistsError,
        FileNotFoundError,
        OSError,
        ValueError,
    ) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        result = execute_rename(store, plan)
    except (
        FileExistsError,
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    message = (
        f"Renamed Context namespace '{plan.old_name}' to '{plan.new_name}' "
        f"({result.renamed_context_count} Context"
        f"{'s' if result.renamed_context_count != 1 else ''})."
    )
    typer.secho(message, fg=typer.colors.GREEN)


__all__ = ["cmd"]
