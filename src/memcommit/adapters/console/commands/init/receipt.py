"""Human-readable console receipt for a completed Context Init."""

from __future__ import annotations

import typer

from memcommit.application.operations.context_init.application import ContextInitResult
from memcommit.adapters.console.terminal.core.text import display_escape_text


def render_context_init(result: ContextInitResult) -> None:
    """Preserve the established successful ``mem init`` output."""

    name = display_escape_text(result.requested_name)
    if not result.create_parents:
        typer.secho(f"Initialized context '{name}'.", fg=typer.colors.GREEN)
        return

    typer.secho(
        f"Ensured context hierarchy '{name}'.",
        fg=typer.colors.GREEN,
    )
    created = ", ".join(
        display_escape_text(created_name) for created_name in result.created_names
    )
    typer.echo("  Created: " + (created if created else "(none)"))
    if result.reused_names:
        typer.echo(
            "  Reused: "
            + ", ".join(
                display_escape_text(reused_name)
                for reused_name in result.reused_names
            )
        )
    typer.echo(f"  Current: {display_escape_text(result.current_name)}")
