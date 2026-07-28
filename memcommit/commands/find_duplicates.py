"""Find duplicate direct Memories without modifying the Context."""
from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.findings_render import (
    render_heading,
    render_memory,
    render_reason,
)
from memcommit.findings import FindingsError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore


_RELATION_COLORS = {
    "EXACT": typer.colors.GREEN,
    "SURFACE_EQUIVALENT": typer.colors.GREEN,
    "SEMANTIC_EQUIVALENT": typer.colors.YELLOW,
    "OVERLAP": typer.colors.CYAN,
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
    """Report duplicate evidence; never merge, remove, or checkpoint it."""
    store = MemoryStore(create=False)
    try:
        ctx = (
            store.load_current_direct()
            if context_name is None
            else store.load_direct(context_name)
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Find duplicates error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        report = ops.find_duplicates(ctx, connect_codex_chatgpt_provider)
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            f"Find duplicates error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    render_heading(
        context_name=ctx.name,
        memory_count=report.memory_count,
        finding_count=len(report.findings),
    )
    if not report.findings:
        typer.echo("\n  (no duplicate findings)")
        return

    for finding in report.findings:
        typer.echo()
        typer.secho(
            f"  DUPLICATE  {finding.relation}",
            fg=_RELATION_COLORS.get(finding.relation, typer.colors.YELLOW),
            bold=True,
        )
        render_memory("LEFT", finding.left)
        render_memory("RIGHT", finding.right)
        render_reason(finding.reason)
