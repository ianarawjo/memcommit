"""Plain command-line presenter for current Context orientation."""

from __future__ import annotations

import typer

from memcommit.current_context_application import CurrentContextResult


def render_current_context(result: CurrentContextResult) -> None:
    """Print the canonical Context name as one script-friendly line."""

    typer.echo(result.context_name)
