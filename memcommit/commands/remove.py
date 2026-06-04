from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.context import Context, Memory
from memcommit.store import MemoryStore


def cmd(uid: Annotated[str, typer.Argument(help="UID (or unambiguous prefix) of the item to remove")]) -> None:
    store = MemoryStore()
    try:
        ctx = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        item = ops.remove(ctx, uid)
    except (KeyError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    store.save(ctx)

    if isinstance(item, Memory):
        typer.secho(f"Removed [{item.uid[:8]}] {item.content}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Removed embedded context '{item.name}' [{item.uid[:8]}]", fg=typer.colors.GREEN)
