"""Shared console failure and terminal detection for Profile commands."""

from __future__ import annotations

import sys

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text


def _fail(error: Exception) -> None:
    typer.secho(
        f"Error: {display_escape_text(str(error))}",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(1)


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()
