"""Render exact Dedup completion and no-change receipts."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.duplicates.dedup.application import (
    ExactDedupScopeReceipt,
)


def render_dedup_receipt(receipt: ExactDedupScopeReceipt) -> None:
    """Print direct or recursive cleanup counts, checkpoints, and recovery."""

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
    typer.echo(f"Checkpoint [{direct_receipt.checkpoint_uid[:8]}] · recovery: mem undo")
