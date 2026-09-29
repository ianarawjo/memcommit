"""Remove same-role exact duplicate direct items without semantic inference."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.duplicates.find_redundancies.receipt.dedup import (
    render_dedup_receipt,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.application.operations.duplicates.dedup.application import (
    ExactDedupError,
    apply_exact_dedup_scope,
)
from memcommit.application.operations.duplicates.find_duplicates.application import (
    analyze_exact_duplicate_scope,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(help="Context to deduplicate (defaults to current)"),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Deduplicate the exact Context root only (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Deduplicate each local lexical descendant independently and "
                "publish the subtree as one Undoable command"
            ),
        ),
    ] = False,
) -> None:
    """Remove later same-role exact items, retaining the first existing UID."""

    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except (TypeError, ValueError) as error:
        typer.secho(
            "Dedup error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    active_store = MemoryStore(create=False)
    try:
        snapshot = ContextOperandSnapshot.capture(active_store)
        access = resolve_existing_context_access(
            active_store,
            context_name,
            current_name=snapshot.current_name,
            required_permission="READ",
        ).value
        analysis = analyze_exact_duplicate_scope(
            active_store,
            access,
            include_descendants=preset is ContextScopePreset.RECURSIVE,
        )
        receipt = apply_exact_dedup_scope(
            active_store,
            access,
            analysis,
        )
    except (
        ConcurrentContextUpdateError,
        ExactDedupError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Dedup error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    render_dedup_receipt(receipt)


__all__ = ["cmd"]
