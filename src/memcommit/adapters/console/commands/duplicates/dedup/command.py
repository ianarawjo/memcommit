"""Deduplicate the current Context, optionally including its descendants."""

from typing import Annotated

import typer

from memcommit.adapters.console.commands.duplicates.find_redundancies import (
    command as find_redundancies,
)
from memcommit.adapters.console.commands.duplicates.find_redundancies.receipt.dedup import (
    render_dedup_receipt,
)
from memcommit.adapters.console.commands.duplicates.find_redundancies.receipt.dedun import (
    render_recursive_dedup_receipt,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.operations.duplicates.dedup.application import (
    apply_exact_dedup_scope,
)
from memcommit.application.operations.duplicates.dedup.recursive import (
    run_recursive_dedup,
)
from memcommit.application.operations.duplicates.find_duplicates.application import (
    analyze_exact_duplicate_scope,
)
from memcommit.persistence.store import ProfileStore


def cmd(
    literal: Annotated[
        bool,
        typer.Option(
            "--literal", help="Remove only identical stored text without LLM inference"
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Compare Memories across the current Context and all descendants; "
                "keep the first by Context depth, Context name, then Memory order"
            ),
        ),
    ] = False,
) -> None:
    """Remove duplicate Memories while preserving the first existing UID and content."""
    try:
        if not literal:
            find_redundancies.run_dedun(
                context_name=None, include_descendants=recursive
            )
            return
        store = ProfileStore(create=False)
        current_name = store.current_context_name()
        if current_name is None:
            raise ValueError(
                "No current Context. Run 'mem switch' or 'mem init' first."
            )
        if recursive:
            with CommandProgress(
                "DEDUP", "comparing combined subtree Memories", total=1
            ):
                _analysis, receipt = run_recursive_dedup(
                    store,
                    current_name,
                    find_redundancies.connect_semantic_provider,
                    literal=True,
                )
            render_recursive_dedup_receipt(receipt, literal=True)
            return
        access = resolve_context_access(store, current_name, current_name=current_name)
        analysis = analyze_exact_duplicate_scope(
            store, access, include_descendants=False
        )
        receipt = apply_exact_dedup_scope(store, access, analysis)
        render_dedup_receipt(receipt)
    except typer.Exit:
        raise
    except Exception as error:
        typer.secho(
            "Dedup error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


__all__ = ["cmd"]
