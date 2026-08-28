"""Plain terminal receipt for an applied structural Merge."""

from __future__ import annotations

import typer

from memcommit.adapters.console.text import display_escape_text
from memcommit.application.operations.merge.application import (
    MergeDecision,
    MergeResult,
)
from memcommit.application.operations.merge.runtime import merge_summary


def render_merge_receipt(result: MergeResult) -> None:
    """Report why Merge changed or retained each classified item set."""

    keep_count = sum(
        resolution.decision is MergeDecision.KEEP_TARGET
        for resolution in result.resolutions
    )
    take_count = len(result.resolutions) - keep_count
    created = sum(context.target_created for context in result.contexts)
    target_changed = bool(result.additions or take_count or created)
    new_detail = f" ({merge_summary(result.additions)})" if result.additions else ""
    typer.secho(
        "MERGE RECORDED · "
        f"'{display_escape_text(result.source_name)}' → "
        f"'{display_escape_text(result.target_name)}' · {result.reach.value} · "
        f"NEW {len(result.additions)}{new_detail} · "
        f"ALREADY PRESENT {len(result.unchanged)} · "
        f"KEPT TARGET {keep_count} · TOOK SOURCE {take_count} · "
        f"CREATED CONTEXTS {created} · "
        f"TARGET CHANGED {'YES' if target_changed else 'NO'} · "
        f"CHECKPOINTS {len(result.checkpoint_uids)}",
        fg=typer.colors.GREEN,
    )
