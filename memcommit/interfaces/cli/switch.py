"""Plain console projection for a typed Switch receipt."""

from __future__ import annotations

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.switch_application import SwitchContextResult


def render_switch_context(result: SwitchContextResult) -> None:
    """Preserve established successful ``mem switch`` wording."""

    name = display_escape_text(result.context_name)
    if not result.changed:
        typer.echo(f"Already on '{name}'.")
        return
    typer.secho(f"Switched to context '{name}'.", fg=typer.colors.GREEN)
