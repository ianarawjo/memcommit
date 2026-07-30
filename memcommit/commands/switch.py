from typing import Annotated, Optional

import typer

from memcommit.commands.context_picker import choose_context
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


def _is_relative_selector(name: str) -> bool:
    """Return whether ``name`` opts into current-Context-relative lookup."""
    return name in {".", ".."} or name.startswith(("./", "../"))


def _resolve_relative_selector(name: str, current: str) -> str:
    """Resolve an explicit lexical selector against one canonical name."""
    parts = current.split("/")
    selector_parts = name.split("/")
    # Match familiar shell spelling: a single trailing slash does not change
    # the destination (`../` is the same node as `..`). Repeated or interior
    # empty segments remain invalid rather than being silently normalized.
    if selector_parts[-1] == "":
        selector_parts.pop()

    if not selector_parts or any(part == "" for part in selector_parts):
        raise ValueError(
            f"relative Context selector '{name}' contains an empty segment."
        )

    for part in selector_parts:
        if part == ".":
            continue
        if part == "..":
            if not parts:
                raise ValueError(
                    f"relative Context selector '{name}' escapes above the "
                    "namespace root."
                )
            parts.pop()
            continue
        parts.append(part)

    if not parts:
        raise ValueError(
            f"relative Context selector '{name}' resolves to the namespace "
            "root, which is not a Context."
        )
    return "/".join(parts)


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
    if _is_relative_selector(selector):
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
            name = _resolve_relative_selector(selector, expected_current)
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
