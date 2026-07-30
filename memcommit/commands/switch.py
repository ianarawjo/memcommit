from typing import Annotated, Optional

import typer

from memcommit.commands.context_picker import choose_context
from memcommit.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Canonical Context name, or an explicit lexical relative "
                "selector such as '.', '..', './child', or '../sibling'; "
                "omit to choose interactively"
            )
        ),
    ] = None,
) -> None:
    store = MemoryStore()
    expected_current = store.current_context_name()
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
                current=expected_current,
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

    selector = name
    if is_relative_context_locator(selector):
        if expected_current is None:
            typer.secho(
                f"Error: cannot switch to '{selector}': no current context is "
                "set.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if selector == ".." and "/" not in expected_current:
            typer.secho(
                f"Error: context '{expected_current}' has no namespace parent.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            name = resolve_context_locator(
                selector,
                current=expected_current,
            )
        except ValueError as error:
            typer.secho(
                f"Error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        # Slash namespaces are lexical only. Explicit Context embeddings are
        # not unique filesystem-style parents and never affect relative paths.
        if selector == ".." and not store.context_exists(name):
            typer.secho(
                f"Error: namespace parent context '{name}' does not exist.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

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
        target = store.load(name)
    except (OSError, ValueError) as e:
        typer.secho(
            f"Error: cannot switch to context '{name}': {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        # Bind both the target record and the current-state snapshot. Without
        # this CAS, a concurrent switch could be silently overwritten after a
        # relative selector or picker result was resolved.
        store.set_current_context_if(
            expected_current,
            name,
            expected_context_uid=target.uid,
            expected_context_digest=target._store_digest or "",
        )
    except (ConcurrentContextUpdateError, OSError, ValueError) as error:
        typer.secho(
            f"Error: cannot switch to context '{name}': {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if expected_current == name:
        typer.echo(f"Already on '{name}'.")
        return
    typer.secho(f"Switched to context '{name}'.", fg=typer.colors.GREEN)
