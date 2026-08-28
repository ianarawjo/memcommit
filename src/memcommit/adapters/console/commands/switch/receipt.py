"""Human-readable console receipt for a completed Context Switch."""

from __future__ import annotations

import typer

from memcommit.adapters.console.text import display_escape_text
from memcommit.application.operations.switch.application import SwitchContextResult


def render_switch_context(result: SwitchContextResult) -> None:
    """Preserve established successful ``mem switch`` wording."""

    name = display_escape_text(result.context_name)
    if not result.changed:
        typer.echo(f"Already on '{name}'.")
        return
    typer.secho(f"Switched to context '{name}'.", fg=typer.colors.GREEN)


__all__ = ["render_switch_context"]
