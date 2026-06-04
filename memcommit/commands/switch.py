from typing import Annotated

import typer

from memcommit.store import ContextStore


def cmd(name: Annotated[str, typer.Argument(help="Name of the context to switch to")]) -> None:
    store = ContextStore()
    if not store.context_exists(name):
        typer.secho(f"Error: context '{name}' does not exist.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if store.current_context_name() == name:
        typer.echo(f"Already on '{name}'.")
        return
    store.set_current(name)
    typer.secho(f"Switched to context '{name}'.", fg=typer.colors.GREEN)
