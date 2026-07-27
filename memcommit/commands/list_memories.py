from typing import Annotated, Optional

import typer

from memcommit.context import Context, MemoryRef
from memcommit.store import MemoryStore


def render_index(ctx: Context) -> None:
    """Print a compact index of a context's direct children."""
    typer.secho(f"Context: {ctx.name}", bold=True)
    count = len(ctx.memories)
    typer.echo(f"  {count} item{'s' if count != 1 else ''}")

    if not ctx.memories:
        typer.echo("\n  (no items)")
        return

    typer.echo()
    for info in ctx.iter_items():
        if isinstance(info, Context):
            typer.echo(f"  [context {info.uid[:8]}] {info.name}")
        elif isinstance(info, MemoryRef):
            state = "" if info.is_resolved else " (dangling)"
            typer.echo(
                f"  [ref     {info.uid[:8]}] "
                f"{info.target_context_name}#{info.target_memory_uid[:8]}{state}"
            )
        else:
            typer.echo(f"  [memory  {info.uid[:8]}] (untitled)")


def cmd(
    context_name: Annotated[Optional[str], typer.Argument(help="Context to list (defaults to current)")] = None,
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

    render_index(store.load(context_name))
