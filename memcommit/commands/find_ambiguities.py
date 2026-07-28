"""Find ambiguous or underspecified direct Memories without modifying them."""
from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.findings_render import (
    render_heading,
    render_memory,
    render_question,
    render_reason,
    render_values,
)
from memcommit.findings import FindingsError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore


_CLARIFICATION_COLORS = {
    "NONE": typer.colors.GREEN,
    "HELPFUL": typer.colors.YELLOW,
    "REQUIRED": typer.colors.RED,
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
    """Report per-Memory ambiguity; never edit or checkpoint the Context."""
    store = MemoryStore(create=False)
    try:
        ctx = (
            store.load_current_direct()
            if context_name is None
            else store.load_direct(context_name)
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Find ambiguities error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        report = ops.find_ambiguities(ctx, connect_codex_chatgpt_provider)
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            f"Find ambiguities error: {error}",
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
        typer.echo("\n  (no ambiguity findings)")
        return

    for finding in report.findings:
        typer.echo()
        typer.secho(
            f"  AMBIGUITY  {finding.interpretation} / "
            f"{finding.clarification}",
            fg=_CLARIFICATION_COLORS.get(
                finding.clarification,
                typer.colors.YELLOW,
            ),
            bold=True,
        )
        render_memory("MEMORY", finding.memory)
        render_values("Ordinary readings", finding.ordinary_readings)
        render_reason(finding.reason)
        render_question(finding.question)
