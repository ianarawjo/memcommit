from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.store import MemoryStore


def cmd(name: Annotated[str, typer.Argument(help="Unique name for the new context")]) -> None:
    store = MemoryStore()
    if store.context_exists(name):
        typer.secho(f"Error: context '{name}' already exists.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    ctx = ops.init(name)
    store.save(ctx)
    store.set_current(name)
    typer.secho(f"Initialized context '{name}'.", fg=typer.colors.GREEN)
