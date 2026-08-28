"""Compact console receipt for a completed Distill proposal."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.distill.application import DistillResult


def render_distill_receipt(result: DistillResult) -> None:
    """Report a bounded proposal result while keeping detail explicitly opt-in."""

    analysis = result.analysis
    overview = " ".join(safe_terminal_text(analysis.overview).split())
    if len(overview) > 280:
        overview = overview[:279].rstrip() + "…"
    typer.echo(
        "\n".join(
            [
                f"DISTILL PROPOSAL · {safe_terminal_text(analysis.source.context_name)}",
                f"UNDERSTOOD · {overview}",
                f"PROPOSED · {len(analysis.rules)} rules",
                f"ATTENTION · {len(analysis.outside_memory_uids)} source Memories outside proposed Rules",
                "DETAILS · rerun with --plain or --tui",
                "SOURCE · UNCHANGED",
            ]
        )
    )


__all__ = ["render_distill_receipt"]
