"""Compatibility facade for neutral Compare execution."""

from __future__ import annotations

from memcommit.comparison_execution import (
    COMPARISON_AGGREGATE_TIMEOUT_SECONDS,
    ComparisonExecutionResult,
    connect_comparison_provider,
    ensure_comparison_analysis,
    install_prepared_comparison_analysis,
    load_comparison_context,
    recursive_comparison_projection,
)


__all__ = [
    "COMPARISON_AGGREGATE_TIMEOUT_SECONDS",
    "ComparisonExecutionResult",
    "connect_comparison_provider",
    "ensure_comparison_analysis",
    "install_prepared_comparison_analysis",
    "load_comparison_context",
    "recursive_comparison_projection",
]
