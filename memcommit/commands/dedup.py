"""Remove same-role exact duplicate direct items without semantic inference."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.authority.access import resolve_context_access
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.exact_dedup_application import ExactDedupError, apply_exact_dedup
from memcommit.interfaces.console.text import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(help="Context to deduplicate (defaults to current)"),
    ] = None,
) -> None:
    """Remove later same-role exact items, retaining the first existing UID."""

    active_store = MemoryStore(create=False)
    try:
        snapshot = ContextOperandSnapshot.capture(active_store)
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=snapshot.current_name,
            required_permission="READ",
        )
        context = access.store.load_direct(access.context_name)
        receipt = apply_exact_dedup(access, context)
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

    context_label = display_escape_text(receipt.context_name)
    if receipt.removed_count == 0:
        typer.echo(f"No exact duplicate direct items in '{context_label}'.")
        return
    typer.secho(
        f"Deduplicated '{context_label}': removed {receipt.removed_count} exact "
        f"duplicate direct item(s); kept {len(receipt.groups)} original UID(s).",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Checkpoint [{receipt.checkpoint_uid[:8]}] · recovery: mem undo")


__all__ = ["cmd"]
