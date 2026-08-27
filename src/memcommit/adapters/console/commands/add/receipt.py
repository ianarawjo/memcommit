"""Line-oriented terminal receipts for completed Add results."""

from __future__ import annotations

import typer

from memcommit.application.operations.add.application import AddInputMode, AddResult
from memcommit.adapters.console.text import display_escape_text


def render_add_receipt(result: AddResult, *, mode: AddInputMode) -> None:
    """Present one completed Add without owning command execution."""

    if mode == "SINGLE":
        memory = result.memories[0]
        typer.secho(
            f"Added [{memory.uid[:8]}] {memory.content}",
            fg=typer.colors.GREEN,
        )
        return
    target = display_escape_text(result.context_name)
    if mode == "PASTE":
        typer.secho(
            f"Added {result.count} "
            f"{'Memory' if result.count == 1 else 'Memories'} to '{target}'.",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo(f"Checkpoint [{result.checkpoint_uid[:8]}].")
        return
    if mode == "LINES":
        typer.secho(
            f"Added {result.count} memories to '{target}':",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        typer.secho(
            f"Added {result.count} "
            f"{'Memory' if result.count == 1 else 'Memories'} to '{target}'.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    for memory in result.memories:
        typer.echo(f"  [{memory.uid[:8]}] {memory.content}")
    typer.echo(f"Checkpoint [{result.checkpoint_uid[:8]}].")
