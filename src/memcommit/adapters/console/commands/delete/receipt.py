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
    """Return the established compact TUI receipt for one removed row."""

    if item.kind == "MEMORY":
        assert item.content is not None
        return f'memory [{item.uid[:8]}]: "{item.content[:80]}"'
    if item.kind == "MEMORY_REF":
        assert item.target_context_name is not None
        assert item.target_memory_uid is not None
        return (
            f"Memory Reference [{item.uid[:8]}] to "
            f"'{item.target_context_name}' [{item.target_memory_uid[:8]}]"
        )
    if item.kind == "QUERY_CONTEXT_REF":
        assert item.name is not None
        return f"Query View '{item.name}' [{item.uid[:8]}]"
    assert item.name is not None
    return f"Context '{item.name}' [{item.uid[:8]}] · VIA EMBED"


def render_removed_item(result: DirectItemDeleteResult) -> None:
    """Write one successful direct-item receipt using existing color semantics."""

    item = result.item
    if item.kind == "MEMORY":
        assert item.content is not None
        # Green confirms success; red belongs only to the content that left
        # the Context, matching the CLI diff removal cue.
        typer.echo(
            typer.style(f"Removed [{item.uid[:8]}] ", fg=typer.colors.GREEN)
            + typer.style(item.content, fg=typer.colors.RED)
        )
        return
    typer.secho(
        f"Removed {removed_item_description(item)}.",
        fg=typer.colors.GREEN,
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
