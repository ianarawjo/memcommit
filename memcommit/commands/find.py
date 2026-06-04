from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.store import MemoryStore


def cmd(query: Annotated[str, typer.Argument(help="Natural language query to find matching memories")]) -> None:
    store = MemoryStore()
    try:
        ctx = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        ops.find(ctx, query)
    except NotImplementedError:
        typer.secho("'mem find' is not yet implemented.", fg=typer.colors.YELLOW)
