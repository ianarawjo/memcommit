"""Provider-free read-only discovery of same-role exact direct items."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_read_report_attempt
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.adapters.console.commands.duplicates.find_redundancies.receipt.find_duplicates import (
    render_find_duplicates_receipt,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.application.operations.duplicates.find_duplicates.application import (
    FindDuplicatesRequest,
    find_duplicates,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.capabilities.reviewing.read_report import ReadReportTarget
from memcommit.persistence.store import MemoryStore


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
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Inspect direct items in the exact Context root only (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Inspect each readable lexical descendant as an independent "
                "direct Context frame"
            ),
        ),
    ] = False,
) -> None:
    """Report exact duplicate groups without provider access or mutation."""

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
            "Find Duplicates error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore(create=False)
    try:
        snapshot = ContextOperandSnapshot.capture(store)
        scope = find_duplicates(
            store,
            FindDuplicatesRequest(
                context_name=context_name,
                include_descendants=preset is ContextScopePreset.RECURSIVE,
            ),
            current_name=snapshot.current_name,
        )
        annotate_read_report_attempt(
            ReadReportTarget(
                operation="find-duplicates",
                context_names=tuple(frame.context_name for frame in scope.contexts),
                target_names=(scope.root_name,),
                selection_mode="SINGLE",
                ranges=("RECURSIVE" if scope.include_descendants else "DIRECT",),
            )
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Find Duplicates error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    render_find_duplicates_receipt(scope)


__all__ = ["cmd"]
