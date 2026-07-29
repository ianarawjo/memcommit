"""Shared terminal rendering for impact and update plans."""
from __future__ import annotations

import typer

from memcommit.update import (
    AddOperation,
    EditOperation,
    UpdateSession,
    count_operations,
)


def _render_sources(operation: EditOperation | AddOperation) -> None:
    labels = [
        f"{source.context_name}#{source.memory_uid[:8]}"
        for source in operation.source_refs
    ]
    typer.secho(f"       Sources: {', '.join(labels)}", dim=True)
    typer.secho(f"       Reason: {operation.reason}", dim=True)


def render_plan(
    session: UpdateSession,
    *,
    staged: bool = False,
    applied: bool = False,
) -> None:
    """Render a canonical local plan without trusting model-formatted prose."""
    if staged and applied:
        raise ValueError("A plan cannot be both staged and applied.")
    edits, additions = count_operations(session)
    heading = (
        "Applied update"
        if applied
        else ("Staged update" if staged else "Impact")
    )
    typer.secho(
        f"{heading}: {session.source_name} -> {session.target_name}",
        bold=True,
    )
    typer.echo(
        f"  {edits} edit{'s' if edits != 1 else ''}, "
        f"{additions} addition{'s' if additions != 1 else ''}"
    )

    if not session.operations:
        typer.echo("\n  (no changes needed)")
    for operation in session.operations:
        typer.echo()
        if isinstance(operation, EditOperation):
            typer.secho(
                f"  EDIT  [{operation.memory_uid[:8]}] "
                f"{operation.owner_context_name}",
                fg=typer.colors.YELLOW,
                bold=True,
            )
            for line in operation.old_content.splitlines() or [""]:
                typer.secho(f"       - {line}", fg=typer.colors.RED)
            for line in operation.new_content.splitlines() or [""]:
                typer.secho(f"       + {line}", fg=typer.colors.GREEN)
        else:
            typer.secho(
                f"  ADD   [{operation.memory_uid[:8]}] "
                f"{operation.owner_context_name}",
                fg=typer.colors.GREEN,
                bold=True,
            )
            for line in operation.new_content.splitlines() or [""]:
                typer.echo(f"       + {line}")
        _render_sources(operation)

    typer.echo()
    if applied:
        typer.echo(f"Updated local working copy {session.target_name}.")
        typer.echo(
            "No shared origin was changed. Contribution still requires "
            "mem push or PR."
        )
    elif staged:
        typer.echo(f"Shared {session.target_name} is unchanged.")
    else:
        typer.echo("No changes applied.")
