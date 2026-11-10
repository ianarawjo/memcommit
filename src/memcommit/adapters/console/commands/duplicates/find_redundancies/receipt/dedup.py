"""Render exact Dedup completion and no-change receipts."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.components.inline_diff import (
    render_inline_memory_change_text,
)
from memcommit.adapters.console.terminal.components.quality_find.rendering import plural
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.application.operations.duplicates.dedup.application import (
    ExactDedupScopeReceipt,
)
from memcommit.core.uid_prefixes import extend_uid_prefixes_until_unique


def render_dedup_summary(context_name: str, removed_count: int, group_count: int) -> None:
    """Count actual removals and duplicate groups without implying a remaining total."""
    typer.echo(
        f"DEDUP APPLIED {display_escape_text(context_name)}; removed "
        f"{plural(removed_count, 'duplicate')} across {plural(group_count, 'group')}."
    )


def render_dedup_group(changes: tuple[MemoryChange, ...]) -> None:
    """Show each retained or removed Memory with its original owner and content."""
    typer.echo()
    uid_prefixes = extend_uid_prefixes_until_unique(change.memory_uid for change in changes)
    for change in changes:
        typer.echo(render_inline_memory_change_text(
            change,
            identity=f"[{change.location}:{uid_prefixes[change.memory_uid]}]",
            color=True,
        ))


def render_dedup_receipt(receipt: ExactDedupScopeReceipt) -> None:
    """Print direct or recursive cleanup counts, checkpoints, and recovery."""

    context_label = display_escape_text(receipt.root_name)
    if receipt.removed_count == 0:
        target = "Context subtree" if receipt.include_descendants else "Context"
        typer.echo(f"No exact duplicate direct items in {target} '{context_label}'.")
        return
    render_dedup_summary(receipt.root_name, receipt.removed_count, len(receipt.groups))
    for context_name, group in (
        (frame.context_name, group)
        for frame in receipt.contexts
        for group in frame.groups
    ):
        content = group.content if group.content is not None else group.summary
        render_dedup_group(tuple(
            MemoryChange(
                marker="=" if memory_uid == group.survivor_uid else "-",
                treatment="KEEP" if memory_uid == group.survivor_uid else "REMOVE",
                location=context_name,
                memory_uid=memory_uid,
                before=content,
                after=content if memory_uid == group.survivor_uid else None,
            )
            for memory_uid in (group.survivor_uid, *group.absorbed_uids)
        ))
    typer.echo()
    if receipt.include_descendants:
        typer.echo(
            "Checkpoints "
            + ", ".join(f"[{uid[:8]}]" for uid in receipt.checkpoint_uids)
            + " · recovery: mem undo (one command unit)"
        )
    else:
        checkpoint_uid = receipt.contexts[0].checkpoint_uid
        assert checkpoint_uid is not None
        typer.echo(f"Checkpoint [{checkpoint_uid[:8]}] · recovery: mem undo")
