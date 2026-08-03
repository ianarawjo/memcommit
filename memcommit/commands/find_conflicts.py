"""Find conflicting direct Memory pairs without modifying the Context."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.findings_render import (
    render_heading,
    render_memory,
    render_question,
    render_reason,
    render_values,
)
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.findings import FindingsError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore


_CONFLICT_COLORS = {
    "YES": typer.colors.RED,
    "MAY": typer.colors.YELLOW,
    "NO": typer.colors.GREEN,
}


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to inspect (defaults to current)",
        ),
    ] = None,
) -> None:
    """Report conflicting Memory pairs; never reconcile or checkpoint them."""
    store = MemoryStore(create=False)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        selected_name = context_snapshot.resolve_or_current(context_name)
        if not selected_name:
            raise RuntimeError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        ctx = store.load_direct(selected_name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        typer.secho(
            "Find conflicts error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        report = ops.find_conflicts(ctx, connect_codex_chatgpt_provider)
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            "Find conflicts error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    render_heading(
        context_name=display_escape_text(ctx.name),
        memory_count=report.memory_count,
        pair_count=report.pair_count,
        finding_count=len(report.findings),
    )
    if not report.findings:
        typer.echo("\n  (no conflict findings)")
        return

    for finding in report.findings:
        typer.echo()
        typer.secho(
            f"  CONFLICT  {finding.conflict}",
            fg=_CONFLICT_COLORS.get(finding.conflict, typer.colors.YELLOW),
            bold=True,
        )
        render_memory("LEFT", finding.left)
        render_memory("RIGHT", finding.right)
        render_values("Scope dimensions", finding.scope_dimensions)
        render_reason(finding.reason)
        render_question(finding.question)
