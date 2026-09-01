"""Line-oriented terminal receipts for completed Add results."""

from __future__ import annotations

import typer

from memcommit.application.operations.add.application import AddResult
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    memory_object_color_rgb,
    semantic_color_rgb,
)


def render_add_receipt(result: AddResult) -> None:
    """Present one completed Add without owning command execution."""

    target = display_escape_text(result.context_name)
    action = typer.style(
        "Added",
        fg=semantic_color_rgb(SemanticColorRole.ADD),
        bold=True,
    )
    noun = "Memory" if result.count == 1 else "Memories"
    typer.echo(f"{action} {result.count} {noun} to '{target}'.")

    for memory in result.memories:
        content = typer.style(
            display_escape_text(memory.content),
            fg=memory_object_color_rgb(),
        )
        typer.echo(f"  [{memory.uid[:8]}] {content}")

    checkpoint = typer.style(
        "Checkpoint",
        fg=semantic_color_rgb(SemanticColorRole.HISTORY),
        bold=True,
    )
    typer.echo(f"Operation {checkpoint} [{result.checkpoint_uid[:8]}].")
