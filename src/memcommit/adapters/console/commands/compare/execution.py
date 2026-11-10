"""Compatibility facade for neutral Compare execution."""

from __future__ import annotations

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.execution import (
    ComparisonExecutionResult,
    ensure_comparison_analysis,
    load_comparison_context,
    recursive_comparison_projection,
)


__all__ = [
    "ComparisonExecutionResult",
    "ensure_comparison_analysis",
    "load_comparison_context",
    "recursive_comparison_projection",
]
