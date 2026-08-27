"""Find ambiguous or underspecified direct Memories without modifying them."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.application.ops as ops
from memcommit.adapters.console.commands.shared.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.application.authority.access import GrantedReadStore, resolve_context_access
from memcommit.adapters.interfaces.cli.quality_findings import (
    render_heading,
    render_memory,
    render_question,
    render_readings,
    render_reason,
)
from memcommit.adapters.console.commands.shared.command_progress import CommandProgress
from memcommit.adapters.console.commands.shared.quality_find_workbench import (
    annotate_quality_find_attempt,
    freeze_all_readable_quality_find_source,
    interactive_quality_find_available,
    run_interactive_quality_find,
)
from memcommit.adapters.interfaces.console.text import (
    display_escape_text,
)
from memcommit.adapters.interfaces.console.identity import collision_safe_uid_prefixes
from memcommit.adapters.interfaces.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.application.reviewing.quality.findings import FindingsError
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.reviewing.quality.workbench import QualityFindSourceFrame


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
    all_contexts: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Inspect all readable Contexts in the active Profile",
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
    """Report per-Memory ambiguity; never edit or checkpoint the Context."""
    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
    except ValueError as error:
        typer.secho(
            "Find ambiguities error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore(create=False)
    if all_contexts and context_name is not None:
        typer.secho(
            "Find ambiguities error: --all/-a cannot be combined with an "
            "explicit Context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if select_targets:
        if context_name is not None or all_contexts:
            typer.secho(
                "Find ambiguities error: --select cannot be combined with an "
                "explicit Context or --all/-a.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not interactive_quality_find_available():
            typer.secho(
                "Find ambiguities error: --select requires an interactive terminal.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            context_snapshot = ContextOperandSnapshot.capture(store)
            completed = run_interactive_quality_find(
                store,
                current_name=context_snapshot.current_name,
                kind="ambiguities",
                analyze=lambda source: ops.find_ambiguities(
                    source.analysis_context(),
                    connect_codex_chatgpt_provider,
                    context_name_by_uid=source.memory_context_names,
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
        if all_contexts:
            source = freeze_all_readable_quality_find_source(
                store,
                current_name=context_snapshot.current_name,
            )
        else:
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
            source = QualityFindSourceFrame.create(
                (ctx,),
                context_names=(access.display_name,),
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
            (
                f"analyzing {source.memory_count} direct memories across "
                f"{len(source.contexts)} contexts"
                if all_contexts
                else "analyzing direct memories"
            ),
            total=1,
        ):
            report = ops.find_ambiguities(
                source.analysis_context(),
                connect_codex_chatgpt_provider,
                context_name_by_uid=source.memory_context_names,
            )
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            "Find ambiguities error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    annotate_quality_find_attempt(
        "ambiguities",
        source,
    )

    render_heading(
        operation_label="Find Ambiguities",
        context_name=(
            "ALL READABLE CONTEXTS"
            if all_contexts
            else display_escape_text(source.context_names[0])
        ),
        facts=(
            f"{len(report.findings)}/{report.memory_count} direct memories flagged",
        ),
    )
    if not report.findings:
        return

    uid_prefixes = collision_safe_uid_prefixes(
        finding.memory.uid for finding in report.findings
    )
    for index, finding in enumerate(report.findings, start=1):
        typer.echo()
        label = "UNDERSPECIFIED" if finding.interpretation == "SINGLE" else "AMBIGUITY"
        typer.secho(
            f"  {label} {index}/{len(report.findings)}",
            fg=semantic_color_rgb(SemanticColorRole.QUALITY_AMBIGUITY),
            bold=True,
        )
        render_memory(
            finding.memory,
            uid_prefix=uid_prefixes[finding.memory.uid],
            context_name=(
                source.memory_context_names[finding.memory.uid]
                if all_contexts
                else None
            ),
        )
        render_readings(finding.ordinary_readings)
        render_reason(finding.reason)
        render_question(finding.question)
