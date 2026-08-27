"""Remove same-role exact duplicate direct items without semantic inference."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.application.authority.access import resolve_context_access
from memcommit.adapters.console.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.core.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.application.operations.exact_dedup.application import (
    ExactDedupError,
    apply_exact_dedup_scope,
)
from memcommit.adapters.console.text import display_escape_text
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
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=snapshot.current_name,
            required_permission="READ",
        )
        receipt = apply_exact_dedup_scope(
            active_store,
            access,
            include_descendants=preset is ContextScopePreset.RECURSIVE,
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

    context_label = display_escape_text(receipt.root_name)
    if receipt.removed_count == 0:
        target = "Context subtree" if receipt.include_descendants else "Context"
        typer.echo(f"No exact duplicate direct items in {target} '{context_label}'.")
        return
    if receipt.include_descendants:
        changed_count = len(receipt.checkpoint_uids)
        typer.secho(
            f"Deduplicated subtree '{context_label}': removed "
            f"{receipt.removed_count} exact duplicate direct item(s) from "
            f"{changed_count} of {len(receipt.contexts)} Context(s).",
            fg=typer.colors.GREEN,
        )
        typer.echo(
            "Checkpoints "
            + ", ".join(f"[{uid[:8]}]" for uid in receipt.checkpoint_uids)
            + " · recovery: mem undo (one command unit)"
        )
        return
    direct_receipt = receipt.contexts[0]
    typer.secho(
        f"Deduplicated '{context_label}': removed {direct_receipt.removed_count} exact "
        "duplicate direct item(s); kept "
        f"{len(direct_receipt.groups)} original UID(s).",
        fg=typer.colors.GREEN,
    )
    assert direct_receipt.checkpoint_uid is not None
    typer.echo(
        f"Checkpoint [{direct_receipt.checkpoint_uid[:8]}] · recovery: mem undo"
    )


__all__ = ["cmd"]
