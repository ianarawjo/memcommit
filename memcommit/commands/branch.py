from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.store import MemoryStore


def cmd(name: Annotated[str, typer.Argument(help="Name for the new branch context")]) -> None:
    store = MemoryStore()
    if store.context_exists(name):
        typer.secho(f"Error: context '{name}' already exists.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        ctx = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    source_name = ctx.name
    new_ctx = ops.branch(ctx, name)
    store.save(new_ctx)
    store.copy_checkpoints(source_name, name)
    store.set_current(name)
    typer.secho(f"Branched '{source_name}' → '{name}' and switched to it.", fg=typer.colors.GREEN)
