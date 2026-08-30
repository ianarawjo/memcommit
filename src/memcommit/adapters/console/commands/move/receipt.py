"""Human-readable receipt for a completed Memory Move."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.adapters.console.coordination.copy_and_move.receipt import placement_text
from memcommit.application.operations.copy_and_move.application import (
    MoveMemoriesResult,
)


def render_move_receipt(result: MoveMemoriesResult) -> None:
    """Preserve the established successful ``mem move`` output."""

    target = display_escape_text(result.into_name)
    typer.echo(
        f"MOVED · {result.count} "
        f"{'Memory' if result.count == 1 else 'Memories'} → '{target}' · "
        f"{result.link_policy} LINKS · {placement_text(result)}"
    )
    remove = typer.style(
        "REMOVE",
        fg=semantic_color_rgb(SemanticColorRole.REMOVE),
        bold=True,
    )
    add = typer.style(
        "ADD",
        fg=semantic_color_rgb(SemanticColorRole.ADD),
        bold=True,
    )
    for item in result.items:
        source = display_escape_text(item.source_context_name)
        typer.echo(
            f"  {remove} '{source}' [{item.source_memory_uid[:8]}] · "
            f"{add} '{target}' [{item.into_memory_uid[:8]}]"
        )
    if result.retargeted_link_count:
        typer.echo(f"Retargeted {result.retargeted_link_count} live Memory Embed(s).")
    if result.dangling_link_count:
        typer.echo(
            f"Left {result.dangling_link_count} live Memory Embed(s) dangling "
            "as explicitly requested."
        )
    typer.echo(
        "Checkpoints "
        + ", ".join(
            f"'{display_escape_text(item.context_name)}' [{item.checkpoint_uid[:8]}]"
            for item in result.checkpoints
        )
        + "."
    )


__all__ = ["render_move_receipt"]
