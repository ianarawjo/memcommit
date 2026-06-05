from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint
from memcommit.store import MemoryStore


def cmd(info: Annotated[str, typer.Argument(help="Information to store (quote multi-word strings)")]) -> None:
    store = MemoryStore()
    try:
        ctx = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    mem = ops.add(ctx, info)
    store.save(ctx, AutoCheckpoint(
        command="add",
        args={"content": info},
        description=f'Added: "{info[:80]}"',
    ))
    typer.secho(f"Added [{mem.uid[:8]}] {info}", fg=typer.colors.GREEN)
