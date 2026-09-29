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


def render_dedun_receipt(
    analysis: RedundancyScopeAnalysis,
    receipt: DedunReceipt | DedunScopeReceipt | None,
) -> None:
    """Print the applied receipt, or the unchanged result when no cleanup exists."""

    if isinstance(receipt, DedunScopeReceipt):
        _render_recursive_dedun_receipt(receipt)
        return
    context_label = display_escape_text(analysis.source.context_names[0])
    if receipt is None:
        typer.echo(f"No redundancies in '{context_label}'.")
        return
    report = analysis.contexts[0].report
    typer.secho(
        f"Dedun '{context_label}': absorbed {len(receipt.absorbed_uids)} "
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


def _render_recursive_dedun_receipt(receipt: DedunScopeReceipt) -> None:
    root = display_escape_text(receipt.root_name)
    if not receipt.absorbed_uids:
        typer.echo(
            f"No redundancies under '{root}' "
            f"({_count(len(receipt.contexts), 'Context')} checked)."
        )
        return
    changed = tuple(frame for frame in receipt.contexts if frame.checkpoint_uid)
    typer.secho(
        f"Dedun '{root}' recursively: absorbed "
        f"{len(receipt.absorbed_uids)} redundant direct item(s) in "
        f"{len(changed)}/{len(receipt.contexts)} Context(s); kept "
        f"{len(receipt.survivor_uids)} original UID(s).",
        fg=typer.colors.GREEN,
    )
    for frame in changed:
        typer.echo(
            f"CONTEXT · {display_escape_text(frame.context_name)} · "
            f"{len(frame.absorbed_uids)} absorbed · checkpoint "
            f"[{frame.checkpoint_uid[:8]}] · review: "
            f"mem review dedun --receipt {frame.checkpoint_uid}"
        )
    assert receipt.operation_uid is not None
    typer.echo(
        f"Operation [{receipt.operation_uid[:8]}] · recovery: "
        "mem undo (one command unit)"
    )
