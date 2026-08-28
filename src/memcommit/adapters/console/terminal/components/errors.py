"""Shared line-oriented error presentation for terminal commands."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text


def render_cli_error(error: object) -> None:
    """Render one terminal-safe error line without framework-owned chrome."""

    typer.secho(
        f"Error: {display_escape_text(str(error))}",
        fg=typer.colors.RED,
        err=True,
    )
