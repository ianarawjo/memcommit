"""Find conflicting direct Memory pairs without modifying the Context."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.conflict_resolve_handoff import (
    run_conflict_resolve_handoff,
)
from memcommit.commands.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
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
    annotate_quality_find_attempt,
    interactive_quality_find_available,
    run_interactive_quality_find,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.findings import FindingsError
from memcommit.fit_judgment import FitJudgmentError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.resolve_application import ResolveError
from memcommit.quality_find_workbench import (
    QualityFindSourceFrame,
    create_quality_find_workbench,
)
from memcommit.quality_finding_handoff import (
    quality_finding_handoff_json,
    quality_finding_handoffs,
)


_CONFLICT_COLORS = {
    "YES": typer.colors.RED,
    "MAY": typer.colors.YELLOW,
    "NO": typer.colors.GREEN,
}


def cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="CONTEXT",
            help="Context to inspect (defaults to current)",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to inspect (defaults to current)",
        ),
    ] = None,
    handoff_json: Annotated[
        bool,
        typer.Option(
            "--handoff-json",
            help="Print one canonical JSON handoff per finding",
        ),
    ] = False,
    select_targets: Annotated[
        bool,
        typer.Option(
            "--select",
            help="Choose readable Context targets and lexical reach interactively",
        ),
    ] = False,
) -> None:
    """Report conflicting Memory pairs; never reconcile or checkpoint them."""
    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
    except ValueError as error:
        typer.secho(
            "Find conflicts error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore(create=False)
    if select_targets:
        if context_name is not None or handoff_json:
            typer.secho(
                "Find conflicts error: --select cannot be combined with "
                "an explicit Context or --handoff-json.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not interactive_quality_find_available():
            typer.secho(
                "Find conflicts error: --select requires an interactive terminal.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            context_snapshot = ContextOperandSnapshot.capture(store)
            completed = run_interactive_quality_find(
                store,
                current_name=context_snapshot.current_name,
                kind="conflicts",
                analyze=lambda source: ops.find_conflicts(
                    source.analysis_context(),
                    connect_codex_chatgpt_provider,
                    context_name_by_uid=source.memory_context_names,
                ),
                handoff_handler=lambda handoff: run_conflict_resolve_handoff(
                    store,
                    current_name=context_snapshot.current_name,
                    handoff=handoff,
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
            FitJudgmentError,
            QueryProviderError,
            ResolveError,
        ) as error:
            typer.secho(
                "Find conflicts error: " + display_escape_text(str(error)),
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not completed:
            typer.echo("Find conflicts cancelled.")
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
            "Find conflicts error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        with CommandProgress(
            "FIND CONFLICTS",
            "analyzing direct memories",
            total=1,
        ):
            report = ops.find_conflicts(ctx, connect_codex_chatgpt_provider)
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            "Find conflicts error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    source = QualityFindSourceFrame.create(
        (ctx,),
        context_names=(access.display_name,),
    )
    annotate_quality_find_attempt("conflicts", source)

    if handoff_json:
        session = create_quality_find_workbench("conflicts", source, report)
        for handoff in quality_finding_handoffs(session):
            typer.echo(quality_finding_handoff_json(handoff))
        return

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
