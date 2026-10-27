"""Application boundary for one transient lightweight Compare result."""

from __future__ import annotations


from collections.abc import Callable

from memcommit.application.context_access.access import (
    ContextAccess,
    resolve_context_access,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    ComparisonInput,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository import (
    ConcurrentComparisonUpdateError,
)
from memcommit.application.operations.compare.compare_summary import ComparisonSummary
from memcommit.application.operations.compare.provider_contract import (
    ComparisonSummaryProvider,
    summarize_comparison,
)
from memcommit.models.context import Context
from memcommit.persistence.store import ProfileStore


def run_comparison_summary(
    *,
    store: ProfileStore,
    reference_access: ContextAccess,
    compared_access: ContextAccess,
    reference: Context,
    compared: Context,
    current_name: str | None,
    include_descendants: tuple[bool, bool] = (False, False),
    memory_selectors: tuple[str | None, str | None] = (None, None),
    provider_factory: Callable[[], ComparisonSummaryProvider],
    context_loader: Callable[..., Context],
) -> ComparisonSummary:
    """Synthesize, revalidate, and return without retaining an artifact."""

    accesses = (reference_access, compared_access)
    comparison_input = ComparisonInput.from_contexts(
        reference,
        compared,
        reference_descendants=include_descendants[0],
        compared_descendants=include_descendants[1],
        reference_memory_selector=memory_selectors[0],
        compared_memory_selector=memory_selectors[1],
    )
    summary = summarize_comparison(comparison_input, provider_factory())

    current_accesses: list[ContextAccess] = []
    for access in accesses:
        current_accesses.append(
            resolve_context_access(
                store, access.context_name, current_name=current_name
            )
        )
    current_reference = context_loader(
        current_accesses[0],
        include_descendants=include_descendants[0],
    )
    current_compared = context_loader(
        current_accesses[1],
        include_descendants=include_descendants[1],
    )
    current_input = ComparisonInput.from_contexts(
        current_reference,
        current_compared,
        reference_descendants=include_descendants[0],
        compared_descendants=include_descendants[1],
        reference_memory_selector=memory_selectors[0],
        compared_memory_selector=memory_selectors[1],
    )
    if not summary.matches_input(current_input):
        raise ConcurrentComparisonUpdateError(
            "A comparison source changed while Compare was summarizing it; "
            "no result was published."
        )
    return summary


__all__ = ["run_comparison_summary"]
