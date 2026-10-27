"""Render the completed Branch result."""

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.branch.application import BranchResult


def render_branch_receipt(result: BranchResult) -> None:
    source_name = display_escape_text(result.source_root)
    target_name = display_escape_text(result.target_root)
    if result.include_descendants:
        typer.secho(
            f"Branched subtree '{source_name}' → '{target_name}' · "
            f"{result.context_count} Context(s), {result.descendant_count} descendant(s); "
            "switched to its root.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"Branched '{source_name}' → '{target_name}' and switched to it.",
            fg=typer.colors.GREEN,
        )
