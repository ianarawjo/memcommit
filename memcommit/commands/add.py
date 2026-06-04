import uuid
from typing import Annotated

import typer

from memcommit.context import Memory
from memcommit.store import ContextStore


def cmd(info: Annotated[str, typer.Argument(help="Information to store (quote multi-word strings)")]) -> None:
    store = ContextStore()
    try:
        ctx = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    mem = Memory(uid=str(uuid.uuid4()), content=info)
    ctx.add(mem)
    store.save_context(ctx)
    typer.secho(f"Added [{mem.uid[:8]}] {info}", fg=typer.colors.GREEN)
