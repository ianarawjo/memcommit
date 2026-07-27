from typing import Annotated, Optional

import typer

from memcommit.context import AutoCheckpoint
from memcommit.store import MemoryStore


def cmd(
    context_name: Annotated[Optional[str], typer.Argument(help="Context to clear (defaults to current)")] = None,
    force: Annotated[bool, typer.Option("-f", "--force", help="Skip confirmation prompt")] = False,
) -> None:
    store = MemoryStore()

    if context_name is None:
        context_name = store.current_context_name()
        if not context_name:
            typer.secho("No current context. Run 'mem init <name>' first.", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    if not store.context_exists(context_name):
        typer.secho(f"Error: context '{context_name}' not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    ctx = store.load(context_name)
    count = len(ctx.memories)

    if count == 0:
        typer.secho(f"Context '{context_name}' is already empty.", fg=typer.colors.YELLOW)
        return

    if not force:
        typer.echo(f"This will remove all {count} item(s) from '{context_name}'.")
        typer.confirm("Continue?", abort=True)

    ctx.clear()
    store.save(ctx, AutoCheckpoint(
        command="clear",
        args={"count": count, "context": context_name},
        description=f"Cleared all {count} item(s) from '{context_name}'",
    ))
    typer.secho(f"Cleared {count} item(s) from '{context_name}'.", fg=typer.colors.GREEN)
