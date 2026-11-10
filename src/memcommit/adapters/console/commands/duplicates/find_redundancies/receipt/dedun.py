"""Render direct or atomic recursive Dedun outcomes."""

from __future__ import annotations

import typer

from memcommit.adapters.console.commands.duplicates.find_redundancies.receipt.dedup import (
    render_dedup_group,
    render_dedup_summary,
)
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
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.application.capabilities.semantic_execution.relations import (
    connected_relation_components,
)


def _render_applied_dedup_groups(
    analysis: RedundancyScopeAnalysis | DedupScopeAnalysis,
    receipt: DedunReceipt | DedunScopeReceipt,
) -> None:
    report = (
        analysis.report
        if isinstance(analysis, DedupScopeAnalysis)
        else analysis.contexts[0].report
    )
    # Use the frozen input: removed Memories no longer exist in the live Context.
    memories = analysis.source.analysis_context().memories
    owner_names = analysis.source.memory_context_names
    removed_uids = set(receipt.absorbed_uids)
    groups = connected_relation_components(
        tuple(memories),
        ((finding.left.uid, finding.right.uid) for finding in report.findings),
    )
    for member_uids in groups:
        if not removed_uids.intersection(member_uids):
            continue
        render_dedup_group(tuple(
            MemoryChange(
                marker="-" if memory_uid in removed_uids else "=",
                treatment="REMOVE" if memory_uid in removed_uids else "KEEP",
                location=owner_names[memory_uid],
                memory_uid=memory_uid,
                before=memories[memory_uid].content,
                after=None if memory_uid in removed_uids else memories[memory_uid].content,
            )
            for memory_uid in member_uids
        ))


def render_dedun_receipt(
    analysis: RedundancyScopeAnalysis | DedupScopeAnalysis,
    receipt: DedunReceipt | DedunScopeReceipt | None,
) -> None:
    """Print the applied receipt, or the unchanged result when no cleanup exists."""

    if isinstance(receipt, DedunScopeReceipt):
        render_recursive_dedup_receipt(analysis, receipt)
        return
    context_name = display_escape_text(analysis.source.context_names[0])
    if receipt is None:
        typer.echo(f"No redundancies in '{context_name}'.")
        return
    render_dedup_summary(
        analysis.source.context_names[0],
        len(receipt.absorbed_uids),
        len(receipt.survivor_uids),
    )
    _render_applied_dedup_groups(analysis, receipt)
    typer.echo()
    typer.echo(
        f"Checkpoint [{receipt.checkpoint_uid[:8]}] · recovery: mem undo"
    )


def render_recursive_dedup_receipt(
    analysis: RedundancyScopeAnalysis | DedupScopeAnalysis,
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
    render_dedup_summary(
        receipt.root_name, len(receipt.absorbed_uids), len(receipt.survivor_uids)
    )
    typer.echo(
        "SCOPE · Combined subtree · KEEP ORDER · "
        "Context depth, Context name, Memory order"
    )
    _render_applied_dedup_groups(analysis, receipt)
    typer.echo()
    for context_receipt in changed_context_receipts:
        typer.echo(
            f"CONTEXT · {display_escape_text(context_receipt.context_name)} · "
            f"{len(context_receipt.absorbed_uids)} removed · checkpoint "
            f"[{context_receipt.checkpoint_uid[:8]}]"
        )
    assert receipt.operation_uid is not None
    typer.echo(
        f"Operation [{receipt.operation_uid[:8]}] · recovery: "
        "mem undo (one command unit)"
    )
