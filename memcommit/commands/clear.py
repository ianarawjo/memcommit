from typing import Annotated, Optional

import typer

from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.context import AutoCheckpoint
from memcommit.store import MemoryStore


def cmd(
    context_name: Annotated[Optional[str], typer.Argument(help="Context to clear (defaults to current)")] = None,
    force: Annotated[bool, typer.Option("-f", "--force", help="Skip confirmation prompt")] = False,
) -> None:
    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    try:
        context_name = snapshot.resolve_or_current(context_name)
        if not context_name:
            raise RuntimeError(
                "No current context. Run 'mem init <name>' first."
            )
        ctx = store.load_direct(context_name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    display_name = display_escape_text(context_name)
    count = len(ctx.memories)

    if count == 0:
        typer.secho(
            f"Context '{display_name}' is already empty.",
            fg=typer.colors.YELLOW,
        )
        return

    if not force:
        typer.echo(f"This will remove all {count} item(s) from '{display_name}'.")
        typer.confirm("Continue?", abort=True)

    ctx.clear()
    store.save(ctx, AutoCheckpoint(
        command="clear",
        args={"count": count, "context": context_name},
        description=f"Cleared all {count} item(s) from '{context_name}'",
    ))
    typer.secho(
        f"Cleared {count} item(s) from '{display_name}'.",
        fg=typer.colors.GREEN,
    )
