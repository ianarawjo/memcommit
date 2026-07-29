from typing import Annotated, Optional

import typer

from memcommit.commands.context_picker import choose_context
from memcommit.store import MemoryStore


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Context name to switch to; use '..' for an existing "
                "namespace parent, or omit to choose interactively"
            )
        ),
    ] = None,
) -> None:
    store = MemoryStore()
    if name is None:
        names = store.list_context_names()
        if not names:
            typer.secho(
                "Error: no contexts exist. Run 'mem init <name>' first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            name = choose_context(
                names,
                current=store.current_context_name(),
            )
        except ValueError as error:
            typer.secho(
                f"Error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if name is None:
            typer.echo("Switch cancelled.")
            return

    if name == "..":
        current = store.current_context_name()
        if current is None:
            typer.secho(
                "Error: cannot switch to '..': no current context is set.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if "/" not in current:
            typer.secho(
                f"Error: context '{current}' has no namespace parent.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        parent = current.rsplit("/", 1)[0]
        # Slash namespaces are lexical only. An explicit Context embedding is
        # not a unique filesystem-style parent and must not affect `..`.
        if not store.context_exists(parent):
            typer.secho(
                f"Error: namespace parent context '{parent}' does not exist.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        name = parent

    # Revalidate after the picker closes: another process may have changed or
    # deleted the selected Context while the terminal UI was open.
    if not store.context_exists(name):
        typer.secho(
            f"Error: context '{name}' does not exist.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        store.load(name)
    except (OSError, ValueError) as e:
        typer.secho(
            f"Error: cannot switch to context '{name}': {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if store.current_context_name() == name:
        typer.echo(f"Already on '{name}'.")
        return
    store.set_current(name)
    typer.secho(f"Switched to context '{name}'.", fg=typer.colors.GREEN)
