from typing import Annotated

import typer

from memcommit.store import MemoryStore


def cmd(
    context_name: Annotated[str, typer.Argument(help="Context to delete")],
    force: Annotated[bool, typer.Option("-f", "--force", help="Skip confirmation prompt")] = False,
) -> None:
    store = MemoryStore()

    if not store.context_exists(context_name):
        typer.secho(f"Error: context '{context_name}' not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not force:
        typer.echo(
            f"This will permanently delete context '{context_name}' and its "
            "checkpoint history, plus its matching atomize analysis and "
            "semantic review artifacts. Descendant contexts will be preserved."
        )
        typer.confirm("Continue?", abort=True)

    try:
        store.delete(context_name)
    except (OSError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.secho(f"Deleted context '{context_name}'.", fg=typer.colors.GREEN)
