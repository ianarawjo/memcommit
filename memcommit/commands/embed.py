from typing import Annotated

import typer

from memcommit.context import Context
from memcommit.store import ContextStore


def cmd(
    a: Annotated[str, typer.Argument(help="Context to embed")],
    into: Annotated[str, typer.Option("--into", help="Target context to embed into")],
) -> None:
    store = ContextStore()
    for name in (a, into):
        if not store.context_exists(name):
            typer.secho(f"Error: context '{name}' does not exist.", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
    if a == into:
        typer.secho("Error: cannot embed a context into itself.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    target = store.load_context(into)
    for info in target.memories.values():
        if isinstance(info, Context) and info.name == a:
            typer.echo(f"'{a}' is already embedded in '{into}'.")
            return

    child = store.load_context(a)
    target.add(child)
    store.save_context(target)
    typer.secho(f"Embedded '{a}' into '{into}'.", fg=typer.colors.GREEN)
