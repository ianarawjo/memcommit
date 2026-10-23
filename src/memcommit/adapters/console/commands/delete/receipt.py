"""Human-readable receipts for the unified Delete operation."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.delete.application import (
    ContextDeleteResult,
    DeletedDirectItem,
    DirectItemDeleteResult,
)


def removed_item_description(item: DeletedDirectItem) -> str:
    """Return the compact TUI receipt for one removed Memory."""

    return f'memory [{item.uid[:8]}]: "{item.content[:80]}"'


def render_removed_item(result: DirectItemDeleteResult) -> None:
    """Write one successful Memory removal receipt."""

    item = result.item
    # Success is green; the removed Memory content keeps the red diff cue.
    typer.echo(
        typer.style(f"Removed [{item.uid[:8]}] ", fg=typer.colors.GREEN)
        + typer.style(item.content, fg=typer.colors.RED)
    )


def render_context_delete_result(result: ContextDeleteResult) -> None:
    """Write a durable ledger receipt, including committed cleanup warnings."""

    name = display_escape_text(result.context_name)
    if result.status == "APPLIED_WITH_CLEANUP_WARNING":
        assert result.cleanup_warning is not None
        typer.secho(
            f"Deleted context '{name}' · ledger [{result.event_uid[:8]}], but "
            "post-delete cleanup was incomplete: "
            f"{display_escape_text(result.cleanup_warning)}",
            fg=typer.colors.YELLOW,
            err=True,
        )
        return
    typer.secho(
        f"Deleted context '{name}' · ledger [{result.event_uid[:8]}].",
        fg=typer.colors.GREEN,
    )


__all__ = [
    "removed_item_description",
    "render_context_delete_result",
    "render_removed_item",
]
