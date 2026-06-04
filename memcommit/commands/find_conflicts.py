from typing import Annotated

import typer

import memcommit.ops as ops
from memcommit.store import MemoryStore


def cmd(info: Annotated[str, typer.Argument(help="Information to check for conflicts against the current context")]) -> None:
    store = MemoryStore()
    try:
        ctx = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        ops.find_conflicts(ctx, info)
    except NotImplementedError:
        typer.secho("'mem find-conflicts' is not yet implemented.", fg=typer.colors.YELLOW)
