"""Compatibility and wait-view adapter for neutral Compare execution."""

from __future__ import annotations

from memcommit.comparison import ComparisonInput
from memcommit.comparison_execution import (
    COMPARISON_AGGREGATE_TIMEOUT_SECONDS,
    ComparisonExecutionResult,
    connect_comparison_provider,
    ensure_comparison_analysis,
    install_prepared_comparison_analysis,
    load_comparison_context,
    recursive_comparison_projection,
)
from memcommit.commands.command_wait import CommandWaitView
from memcommit.interfaces.console.text import display_escape_text


def comparison_wait_view(comparison_input: ComparisonInput) -> CommandWaitView:
    """Restore the exact frozen setup while its report is unavailable."""

    lines = ["MEM COMPARE · FROZEN INPUT · RESULT PENDING", ""]
    labels = ("REFERENCE A", "PEER B")
    for label, frame, descendants in zip(
        labels,
        comparison_input.frames,
        comparison_input.include_descendants,
        strict=True,
    ):
        lines.append(f"{label} · {display_escape_text(frame.context_name)}")
        lines.append(
            "  SCOPE · "
            + ("INCLUDE DESCENDANTS" if descendants else "THIS CONTEXT ONLY")
        )
        lines.append(f"  FROZEN MEMORIES · {len(frame.memories)}")
        lines.append("")
    lines.extend(
        [
            "The comparison report will replace this setup after the provider",
            "returns. The two frozen source frames cannot be changed here.",
        ]
    )
    return CommandWaitView(
        title="COMPARE CONFIRMED INPUTS · READ-ONLY",
        text="\n".join(lines),
    )


__all__ = [
    "COMPARISON_AGGREGATE_TIMEOUT_SECONDS",
    "ComparisonExecutionResult",
    "comparison_wait_view",
    "connect_comparison_provider",
    "ensure_comparison_analysis",
    "install_prepared_comparison_analysis",
    "load_comparison_context",
    "recursive_comparison_projection",
]
