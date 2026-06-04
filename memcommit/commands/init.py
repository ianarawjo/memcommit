import uuid
from typing import Annotated

import typer

from memcommit.context import Context
from memcommit.store import ContextStore


def cmd(name: Annotated[str, typer.Argument(help="Unique name for the new context")]) -> None:
    store = ContextStore()
    if store.context_exists(name):
        typer.secho(f"Error: context '{name}' already exists.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    ctx = Context(uid=str(uuid.uuid4()), name=name)
    store.save_context(ctx)
    store.set_current(name)
    typer.secho(f"Initialized context '{name}'.", fg=typer.colors.GREEN)
