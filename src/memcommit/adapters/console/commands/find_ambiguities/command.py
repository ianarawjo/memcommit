"""Find ambiguous or underspecified direct Memories without modifying them."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.adapters.console.terminal.components.quality_find.rendering import (
    render_heading,
    render_memory,
    render_question,
    render_readings,
    render_reason,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.core.uid_prefixes import (
    extend_uid_prefixes_until_unique,
)
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsError,
)
from memcommit.providers.errors import QueryProviderError
from memcommit.providers.connection import connect_semantic_provider
from memcommit.persistence.store import ProfileStore
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.find_ambiguities.application import (
    FindAmbiguitiesRequest,
    analyze_find_ambiguities,
    prepare_find_ambiguities,
)


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
    store = ProfileStore(create=False)
    if all_contexts and context_name is not None:
        typer.secho(
            "Find ambiguities error: --all/-a cannot be combined with an "
            "explicit Context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        source = prepare_find_ambiguities(
            store,
            FindAmbiguitiesRequest(
                context_name=context_name,
                all_readable=all_contexts,
            ),
            current_name=context_snapshot.current_name,
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
            result = analyze_find_ambiguities(
                source,
                connect_semantic_provider,
            )
            report = result.report
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            "Find ambiguities error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

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

    uid_prefixes = extend_uid_prefixes_until_unique(
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
