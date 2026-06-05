from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint
from memcommit.store import MemoryStore


def cmd(
    a: Annotated[str, typer.Argument(help="Context to embed")],
    into: Annotated[str, typer.Option("--into", help="Target context to embed into")],
) -> None:
    store = MemoryStore()
    for name in (a, into):
        if not store.context_exists(name):
            typer.secho(f"Error: context '{name}' does not exist.", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    child = store.load(a)
    parent = store.load(into)
    try:
        ops.embed(child, parent)
    except ValueError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    store.save(parent, AutoCheckpoint(
        command="embed",
        args={"child": a, "into": into},
        description=f"Embedded '{a}' into '{into}'",
    ))
    typer.secho(f"Embedded '{a}' into '{into}'.", fg=typer.colors.GREEN)
