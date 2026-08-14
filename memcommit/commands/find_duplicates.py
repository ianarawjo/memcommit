"""Find duplicate direct Memories without modifying the Context."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import GrantedReadStore, resolve_context_access
from memcommit.commands.findings_render import (
    render_heading,
    render_memory,
    render_reason,
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
    if context_name is None and interactive_quality_find_available():
        try:
            context_snapshot = ContextOperandSnapshot.capture(store)
            completed = run_interactive_quality_find(
                store,
                current_name=context_snapshot.current_name,
                kind="duplicates",
                analyze=lambda ctx: ops.find_duplicates(
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
                "Find duplicates error: " + display_escape_text(str(error)),
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not completed:
            typer.echo("Find duplicates cancelled.")
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
            "Find duplicates error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        with CommandProgress(
            "FIND DUPLICATES",
            "analyzing direct memories",
            total=1,
        ):
            report = ops.find_duplicates(ctx, connect_codex_chatgpt_provider)
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            "Find duplicates error: " + display_escape_text(str(error)),
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
