"""Application boundary for one transient lightweight Compare result."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.application.operations.compare.ledger.model import ComparisonInput
from memcommit.application.operations.compare.ledger.store import ConcurrentComparisonUpdateError
from memcommit.application.operations.compare.compare_summary import ComparisonSummary
from memcommit.application.operations.compare.provider_contract import (
    ComparisonSummaryProvider,
    summarize_comparison,
)
from memcommit.core.context import Context
from memcommit.application.capabilities.authority.source_use_policy import authorize_combination
from memcommit.application.operations.profile.model import authority_grant_snapshot_lock
from memcommit.persistence.store import MemoryStore


def run_comparison_summary(
    *,
    store: MemoryStore,
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
    authorize_combination(accesses)
    bindings = tuple(
        freeze_granted_context_binding(access) if access.is_granted else None
        for access in accesses
    )
    comparison_input = ComparisonInput.from_contexts(
        reference,
        compared,
        reference_descendants=include_descendants[0],
        compared_descendants=include_descendants[1],
        reference_memory_selector=memory_selectors[0],
        compared_memory_selector=memory_selectors[1],
    )
    summary = summarize_comparison(comparison_input, provider_factory())

    # A transient result has no CAS write to protect its publication. Re-read
    # both local and granted frames so the displayed prose always describes
    # the exact sources that remain readable at the return boundary.
    with authority_grant_snapshot_lock() as registry:
        current_accesses: list[ContextAccess] = []
        for access, binding in zip(accesses, bindings, strict=True):
            current_accesses.append(
                revalidate_granted_context_binding(
                    binding,
                    registry=registry,
                    active_store=store,
                )
                if binding is not None
                else resolve_context_access(
                    store,
                    access.context_name,
                    current_name=current_name,
                    required_permission="READ",
                    registry=registry,
                )
            )
        authorize_combination(current_accesses)
        current_reference = context_loader(
            current_accesses[0],
            include_descendants=include_descendants[0],
            registry=registry,
        )
        current_compared = context_loader(
            current_accesses[1],
            include_descendants=include_descendants[1],
            registry=registry,
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
