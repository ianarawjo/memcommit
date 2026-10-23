"""Line-oriented terminal output for the completed Contexts query."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text


def render_contexts_receipt(
    context_names: tuple[str, ...],
    current_context_name: str | None,
) -> None:
    if not context_names:
        typer.echo("No contexts yet. Run 'mem init <name>' to create one.")
        return

    for name in context_names:
        label = display_escape_text(name)
        marker = "  "
        if name == current_context_name:
            marker = typer.style("* ", fg=typer.colors.GREEN, bold=True)
            label = typer.style(label, fg=typer.colors.GREEN, bold=True)
        typer.echo(f"{marker}       {label}")
