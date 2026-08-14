"""Find ambiguous or underspecified direct Memories without modifying them."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import GrantedReadStore, resolve_context_access
from memcommit.commands.findings_render import (
    render_heading,
    render_memory,
    render_question,
    render_reason,
    render_values,
)
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.quality_find_workbench import (
    interactive_quality_find_available,
    run_interactive_quality_find,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.findings import FindingsError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError


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
    if context_name is None and interactive_quality_find_available():
        try:
            context_snapshot = ContextOperandSnapshot.capture(store)
            completed = run_interactive_quality_find(
                store,
                current_name=context_snapshot.current_name,
                kind="ambiguities",
                analyze=lambda ctx: ops.find_ambiguities(
                    ctx,
                    connect_codex_chatgpt_provider,
                ),
            )
        except (
            FileNotFoundError,
            OSError,
            ProfileConfigError,
            ProfileError,
            RuntimeError,
            ValueError,
            FindingsError,
            QueryProviderError,
        ) as error:
            typer.secho(
                "Find ambiguities error: " + display_escape_text(str(error)),
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not completed:
            typer.echo("Find ambiguities cancelled.")
        return
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        access = resolve_context_access(
            store,
            context_name,
            current_name=context_snapshot.current_name,
            required_permission="READ",
        )
        ctx = (
            GrantedReadStore(access).load_direct(access.display_name)
            if access.is_granted
            else store.load_direct(access.context_name)
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Find ambiguities error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        with CommandProgress(
            "FIND AMBIGUITIES",
            "analyzing direct memories",
            total=1,
        ):
            report = ops.find_ambiguities(ctx, connect_codex_chatgpt_provider)
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            "Find ambiguities error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    render_heading(
        context_name=display_escape_text(ctx.name),
        memory_count=report.memory_count,
        finding_count=len(report.findings),
    )
    if not report.findings:
        typer.echo("\n  (no ambiguity findings)")
        return

    for finding in report.findings:
        typer.echo()
        typer.secho(
            f"  AMBIGUITY  {finding.interpretation} / {finding.clarification}",
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
