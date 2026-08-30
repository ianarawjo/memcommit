"""Context-aware reading analysis for Memory ambiguity."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityReport,
    FindingsProvider,
)
from memcommit.application.capabilities.memory_issue_analysis.provider_contract import (
    find_ambiguities,
)
from memcommit.core.context import Context


def analyze_memory_ambiguities(
    context: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    context_name_by_uid: Mapping[str, str] | None = None,
) -> AmbiguityReport:
    """Judge each direct Memory against the complete supplied Context frame."""

    return find_ambiguities(
        context,
        provider_factory,
        context_name_by_uid=context_name_by_uid,
    )


__all__ = ["analyze_memory_ambiguities"]
