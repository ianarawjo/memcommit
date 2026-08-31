"""Rename one ordinary Context namespace without changing its identities."""
from __future__ import annotations

from typing import Annotated

import typer

from memcommit.application.operations.rename.application import RenameRequest
from memcommit.application.operations.rename.runtime import (
    execute_rename,
    prepare_rename,
)
from memcommit.persistence.store import MemoryStore


def cmd(
    old: Annotated[
        str,
        typer.Argument(
            metavar="OLD",
            help=(
                "Existing portable ordinary Context name, or an explicit lexical "
                "relative selector such as '.', '..', or './child'"
            )
        ),
    ],
    new: Annotated[
        str,
        typer.Argument(
            metavar="NEW",
            help=(
                "New portable canonical Context name; lexical relative selectors "
                "are not accepted"
            )
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "-f",
            "--force",
            help="Skip the confirmation prompt; all safety checks still run",
        ),
    ] = False,
) -> None:
    """Rename OLD and every existing OLD/... descendant to NEW/...."""
    store = MemoryStore()
    # Resolve the source exactly once against one current-state snapshot. NEW
    # is a new identity locator, so the existing-Context resolver must not
    # reinterpret it if global current state changes while approval is open.
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

    if not force:
        typer.echo(
            "This will rename ordinary Context namespace "
            f"'{plan.old_name}' to '{plan.new_name}' "
            f"({len(plan.bindings)} Context"
            f"{'s' if len(plan.bindings) != 1 else ''}, including "
            f"{plan.descendant_count} descendant"
            f"{'s' if plan.descendant_count != 1 else ''})."
        )
        typer.echo(
            "Ordinary Context references, restorable checkpoint pointers, "
            "the current Context pointer, and unapplied Meld bindings will "
            "follow the stable UIDs; query-only Context references are "
            "unchanged."
        )
        if not typer.confirm("Continue?", default=False):
            typer.echo("Rename cancelled.")
            return

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

    typer.secho(
        f"Renamed Context namespace '{plan.old_name}' to '{plan.new_name}' "
        f"({result.renamed_context_count} Context"
        f"{'s' if result.renamed_context_count != 1 else ''}).",
        fg=typer.colors.GREEN,
    )


__all__ = ["cmd"]
