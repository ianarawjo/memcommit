"""Console entry points for redundancy discovery and immediate Dedun."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.duplicates.find_redundancies.receipt.dedun import (
    render_dedun_receipt,
)
from memcommit.adapters.console.commands.duplicates.find_redundancies.receipt.find_redundancies import (
    render_find_redundancies_receipt,
)
from memcommit.adapters.console.coordination.context_operand import (
    choose_context_operand,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.components.quality_find.workbench import (
    annotate_quality_find_attempt,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.memory_issue_analysis.model import FindingsError
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.application.operations.duplicates.find_redundancies.application import (
    FindRedundanciesRequest,
)
from memcommit.application.operations.duplicates.runtime import (
    RedundancyOperation,
    RedundancyRunStage,
    run_redundancies,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore
from memcommit.providers.errors import QueryProviderError
from memcommit.providers.connection import connect_semantic_provider


def _run(
    *,
    context_name: str | None,
    operation: RedundancyOperation,
    evidence_json: bool = False,
    include_descendants: bool = False,
) -> None:
    """Connect console progress and receipts to the application-owned execution."""

    operation_label = "Dedun" if operation == "dedun" else "Find Redundancies"
    store = MemoryStore(create=False)
    try:
        with ExitStack() as progress:

            def on_progress(
                stage: RedundancyRunStage, source: QualityFindSourceFrame
            ) -> None:
                if stage == "analyzing":
                    progress.enter_context(
                        CommandProgress(
                            operation_label.upper(),
                            "analyzing independent direct Context frames",
                            total=len(source.contexts),
                        )
                    )
                else:
                    # Record a completed analysis even if subsequent Apply fails.
                    progress.close()
                    annotate_quality_find_attempt(
                        "duplicates", source, operation_name=operation
                    )

            result = run_redundancies(
                FindRedundanciesRequest(context_name, include_descendants),
                operation=operation,
                store=store,
                provider_factory=connect_semantic_provider,
                on_progress=on_progress,
            )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
        FindingsError,
        QueryProviderError,
    ) as error:
        typer.secho(
            f"{operation_label} error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if operation == "dedun":
        render_dedun_receipt(result.analysis, result.receipt)
    else:
        render_find_redundancies_receipt(result.analysis, evidence_json=evidence_json)


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
    evidence_json: Annotated[
        bool,
        typer.Option(
            "--evidence-json",
            help="Print one canonical redundancy evidence JSON per finding",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Inspect the exact Context root only (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Inspect each readable lexical descendant as an independent "
                "direct semantic frame"
            ),
        ),
    ] = False,
) -> None:
    """Report complete DUN evidence; never change Context content."""
    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except ValueError as error:
        typer.secho(
            "Find Redundancies error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    try:
        _run(
            context_name=context_name,
            evidence_json=evidence_json,
            operation="find-redundancies",
            include_descendants=preset is ContextScopePreset.RECURSIVE,
        )
    except typer.Exit:
        raise
    except ValueError as error:
        typer.secho(
            "Find Redundancies error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def run_dedun(
    *,
    context_name: str | None,
    include_descendants: bool = False,
) -> None:
    """Analyze and immediately apply complete exact-plus-semantic DUN groups."""

    _run(
        context_name=context_name,
        operation="dedun",
        include_descendants=include_descendants,
    )


__all__ = ["cmd", "run_dedun"]
