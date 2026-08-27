"""Typer adapter for ``mem pwd``."""

from __future__ import annotations

import typer

from memcommit.adapters.interfaces.cli.pwd import render_current_context
from memcommit.application.operations.pwd.application import CurrentContextError
from memcommit.application.operations.pwd.runtime import read_current_context
from memcommit.persistence.store import MemoryStore


def cmd() -> None:
    """Print the current Context name without opening or authorizing it."""

    try:
        result = read_current_context(MemoryStore(create=False))
    except (CurrentContextError, OSError, ValueError) as error:
        typer.secho(f"Pwd error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    render_current_context(result)
