from typing import Annotated, Optional

import typer

from memcommit.context import Context, Memory
from memcommit.store import MemoryStore


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

    ctx = store.load(context_name)
    memories = [v for v in ctx.memories.values() if isinstance(v, Memory)]
    embedded = [v for v in ctx.memories.values() if isinstance(v, Context)]

    typer.secho(f"Context: {context_name}", bold=True)
    typer.echo(
        f"  {len(memories)} memor{'y' if len(memories) == 1 else 'ies'}"
        f"  |  {len(embedded)} embedded context{'s' if len(embedded) != 1 else ''}"
    )

    if embedded:
        typer.secho("\nEmbedded contexts:", bold=True)
        for ec in embedded:
            typer.echo(f"  [{ec.uid[:8]}] {ec.name}")

    if memories:
        typer.secho("\nMemories:", bold=True)
        for mem in memories:
            typer.echo(f"  [{mem.uid[:8]}] {mem.content}")
    else:
        typer.echo("\n  (no memories)")
