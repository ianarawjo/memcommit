"""Human-readable console receipt for a completed Context Init."""

from __future__ import annotations

import typer

from memcommit.application.operations.init.application import ContextInitResult
from memcommit.adapters.console.terminal.core.output import echo_text
from memcommit.adapters.console.terminal.core.text import display_escape_text


def render_context_init_receipt(result: ContextInitResult) -> None:
    """Preserve the established successful ``mem init`` output."""

    name = display_escape_text(result.requested_name)
    if not result.create_parents:
        typer.secho(f"Initialized context '{name}'.", fg=typer.colors.GREEN)
        return

    typer.secho(
        f"Ensured context hierarchy '{name}'.",
        fg=typer.colors.GREEN,
    )
    created = ", ".join(result.created_names) or "(none)"
    echo_text("  Created: {names}", names=created)
    if result.reused_names:
        echo_text("  Reused: {names}", names=", ".join(result.reused_names))
    echo_text("  Current: {name}", name=result.current_name)
