"""Render direct or atomic recursive Dedun outcomes."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.components.quality_find.rendering import (
    plural as _count,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.memory_issue_analysis.redundancy_scope import (
    RedundancyScopeAnalysis,
)
from memcommit.application.operations.duplicates.dedun.application import DedunReceipt
from memcommit.application.operations.duplicates.dedun.runtime import DedunScopeReceipt
from memcommit.application.operations.duplicates.dedup.recursive import (
    DedupScopeAnalysis,
)


def render_dedun_receipt(
    analysis: RedundancyScopeAnalysis | DedupScopeAnalysis,
    receipt: DedunReceipt | DedunScopeReceipt | None,
) -> None:
    """Print the applied receipt, or the unchanged result when no cleanup exists."""

    if isinstance(receipt, DedunScopeReceipt):
        render_recursive_dedup_receipt(receipt)
        return
    context_name = display_escape_text(analysis.source.context_names[0])
    if receipt is None:
        typer.echo(f"No redundancies in '{context_name}'.")
        return
    report = analysis.contexts[0].report
    typer.secho(
        f"Dedup '{context_name}': removed {len(receipt.absorbed_uids)} "
        "redundant direct item(s); kept "
        f"{len(receipt.survivor_uids)} original UID(s).",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        "DUN COMPOSITION · "
        f"{_count(report.redundancy_count, 'evidence link')} = "
        f"{_count(report.exact_duplicate_count, 'DUP / EXACT link')} + "
        f"{_count(report.semantic_redundancy_count, 'SEMANTIC DUN link')}"
    )
    typer.echo(
        f"Checkpoint [{receipt.checkpoint_uid[:8]}] · review: "
        f"mem review dedun --receipt {receipt.checkpoint_uid} · "
        "recovery: mem undo"
    )


def render_recursive_dedup_receipt(
    receipt: DedunScopeReceipt, *, literal: bool = False
) -> None:
    root_context_name = display_escape_text(receipt.root_name)
    duplicates_label = "exact duplicates" if literal else "redundancies"
    if not receipt.absorbed_uids:
        typer.echo(
            f"No {duplicates_label} under '{root_context_name}' "
            f"({_count(len(receipt.contexts), 'Context')} checked)."
        )
        return
    changed_context_receipts = tuple(
        context_receipt for context_receipt in receipt.contexts if context_receipt.checkpoint_uid
    )
    removed_label = "exact duplicate" if literal else "redundant"
    typer.secho(
        f"Dedup '{root_context_name}' recursively: removed "
        f"{len(receipt.absorbed_uids)} {removed_label} direct item(s) in "
        f"{len(changed_context_receipts)}/{len(receipt.contexts)} Context(s); kept "
        f"{len(receipt.survivor_uids)} original UID(s).",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        "SCOPE · Combined subtree · KEEP ORDER · "
        "Context depth, Context name, Memory order"
    )
    for context_receipt in changed_context_receipts:
        review = (
            ""
            if literal
            else f" · review: mem review dedun --receipt {context_receipt.checkpoint_uid}"
        )
        typer.echo(
            f"CONTEXT · {display_escape_text(context_receipt.context_name)} · "
            f"{len(context_receipt.absorbed_uids)} removed · checkpoint "
            f"[{context_receipt.checkpoint_uid[:8]}]{review}"
        )
    assert receipt.operation_uid is not None
    typer.echo(
        f"Operation [{receipt.operation_uid[:8]}] · recovery: "
        "mem undo (one command unit)"
    )
