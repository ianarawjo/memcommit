"""Render the receipt for one removed Memory."""

import os

import typer
from memcommit.application.operations.delete.application import (
    ContextDeletePlan,
    ContextDeleteResult,
    DirectItemDeleteResult,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)


def render_context_delete_warning(plan: ContextDeletePlan) -> None:
    typer.echo(
        "This will "
        + typer.style(
            "delete", fg=semantic_color_rgb(SemanticColorRole.REMOVE), bold=True
        )
        + f" Context '{display_escape_text(plan.context_name)}' and all its descendants.\n"
        + "All Memories and checkpoint histories in this subtree will be deleted.\n"
        + typer.style(
            "This cannot be undone with memcommit.",
            fg=semantic_color_rgb(SemanticColorRole.IRREVERSIBLE_WARNING),
        ),
        color=False if "NO_COLOR" in os.environ else None,
    )


def render_context_delete_result(result: ContextDeleteResult) -> None:
    typer.echo(
        typer.style("Deleted", fg=semantic_color_rgb(SemanticColorRole.REMOVE))
        + f" Context '{display_escape_text(result.context_name)}' and "
        + f"{result.deleted_context_count - 1} descendant Context(s).",
        color=False if "NO_COLOR" in os.environ else None,
    )
    if result.cleanup_warning:
        typer.echo(
            "Deletion committed, but cleanup was incomplete: "
            + display_escape_text(result.cleanup_warning),
            err=True,
        )


def render_removed_item(result: DirectItemDeleteResult) -> None:
    """Write one successful Memory removal receipt."""

    item = result.item
    # Success is green; the removed Memory content keeps the red diff cue.
    typer.echo(
        typer.style(f"Removed [{item.uid[:8]}] ", fg=typer.colors.GREEN)
        + typer.style(item.content, fg=typer.colors.RED)
    )
