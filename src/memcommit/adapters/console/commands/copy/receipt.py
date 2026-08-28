"""Human-readable receipt for a completed Memory Copy."""

from __future__ import annotations

import typer

from memcommit.adapters.console.text import display_escape_text
from memcommit.adapters.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.adapters.console.shared.memory_transfer.receipt import placement_text
from memcommit.application.operations.memory_transfer.application import (
    CopyMemoriesResult,
)


def render_copy_receipt(result: CopyMemoriesResult) -> None:
    """Preserve the established successful ``mem copy`` output."""

    action = typer.style(
        "COPIED",
        fg=semantic_color_rgb(SemanticColorRole.ADD),
        bold=True,
    )
    target = display_escape_text(result.into_name)
    typer.echo(
        f"{action} · {result.count} "
        f"{'Memory' if result.count == 1 else 'Memories'} → '{target}' · "
        f"NEW UIDs · {placement_text(result)}"
    )
    for item in result.items:
        source = display_escape_text(item.source_context_name)
        typer.echo(
            f"  '{source}' [{item.source_memory_uid[:8]}] → "
            f"[{item.into_memory_uid[:8]}]"
        )
    typer.echo(
        "Checkpoint "
        + ", ".join(
            f"'{display_escape_text(item.context_name)}' [{item.checkpoint_uid[:8]}]"
            for item in result.checkpoints
        )
        + "."
    )


__all__ = ["render_copy_receipt"]
