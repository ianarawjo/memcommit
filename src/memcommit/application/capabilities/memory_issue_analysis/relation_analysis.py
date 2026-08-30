"""Whole-frame relation analysis for Memory redundancy and conflict."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from memcommit.application.capabilities.memory_issue_analysis.model import (
    ConflictReport,
    DuplicateReport,
    FindingsProvider,
)
from memcommit.application.capabilities.memory_issue_analysis.provider_contract import (
    find_conflicts,
    find_redundancies,
)
from memcommit.core.context import Context


def analyze_memory_redundancies(
    context: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    context_name_by_uid: Mapping[str, str] | None = None,
) -> DuplicateReport:
    """Return removable exact and semantic redundancy evidence."""

    return find_redundancies(
        context,
        provider_factory,
        context_name_by_uid=context_name_by_uid,
    )


def analyze_memory_conflicts(
    context: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    context_name_by_uid: Mapping[str, str] | None = None,
) -> ConflictReport:
    """Return conflicting relations from the complete supplied frame."""

    return find_conflicts(
        context,
        provider_factory,
        context_name_by_uid=context_name_by_uid,
    )


__all__ = ["analyze_memory_conflicts", "analyze_memory_redundancies"]
