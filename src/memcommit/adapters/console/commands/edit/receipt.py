"""Render one exact Memory edit and its before/after content."""

import typer
from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.application.operations.edit.application import EditResult


def _render_content(prefix: str, content: str, color: str) -> None:
    lines = content.splitlines() or [""]
    for line in lines:
        typer.secho(f"  {prefix} {line}", fg=color)


def render_edit_receipt(result: EditResult) -> None:
    if not result.changed:
        annotate_command_outcome("NO_CHANGE")
        typer.secho(
            f"Memory [{result.memory_uid[:8]}] is unchanged.",
            fg=typer.colors.YELLOW,
        )
        return
    typer.secho(
        f"Edited [{result.memory_uid[:8]}] in '{result.context_name}':",
        fg=typer.colors.GREEN,
        bold=True,
    )
    _render_content("-", result.original_content, typer.colors.RED)
    _render_content("+", result.content, typer.colors.GREEN)
