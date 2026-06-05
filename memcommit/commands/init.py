from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint
from memcommit.store import MemoryStore


def cmd(name: Annotated[str, typer.Argument(help="Unique name for the new context")]) -> None:
    store = MemoryStore()
    if store.context_exists(name):
        typer.secho(f"Error: context '{name}' already exists.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    ctx = ops.init(name)
    store.save(ctx, AutoCheckpoint(
        command="init",
        args={"name": name},
        description=f"Initialized context '{name}'",
    ))
    store.set_current(name)
    typer.secho(f"Initialized context '{name}'.", fg=typer.colors.GREEN)
