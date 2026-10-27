"""Run Find Redundancies or Dedun through one frozen analysis."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsProvider,
)
from memcommit.application.capabilities.memory_issue_analysis.redundancy_scope import (
    RedundancyScopeAnalysis,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.operations.duplicates.dedun.application import (
    DEDUN_ELIGIBLE_RELATIONS,
    DedunReceipt,
    DedunRequest,
    apply_dedun,
    prepare_dedun,
    recommended_dedun_selections,
)
from memcommit.application.operations.duplicates.dedun.runtime import (
    DedunScopeReceipt,
    MemoryStoreDedunPort,
)
from memcommit.application.operations.duplicates.dedup.recursive import (
    DedupScopeAnalysis,
    run_recursive_dedup,
)
from memcommit.application.operations.duplicates.find_redundancies.application import (
    FindRedundanciesRequest,
    analyze_find_redundancies,
    prepare_find_redundancies,
)
from memcommit.persistence.store import ProfileStore

RedundancyOperation = Literal["find-redundancies", "dedun"]
RedundancyRunStage = Literal["analyzing", "analyzed"]


@dataclass(frozen=True)
class RedundancyRunResult:
    """The complete analysis and, for an applied Dedun, its durable receipt."""

    analysis: RedundancyScopeAnalysis | DedupScopeAnalysis
    receipt: DedunReceipt | DedunScopeReceipt | None = None


def run_redundancies(
    request: FindRedundanciesRequest,
    *,
    operation: RedundancyOperation,
    store: ProfileStore,
    provider_factory: Callable[[], FindingsProvider],
    on_progress: Callable[[RedundancyRunStage, QualityFindSourceFrame], None]
    | None = None,
) -> RedundancyRunResult:
    """Freeze inputs, analyze once, and apply only an explicitly requested Dedun."""
    if not isinstance(request, FindRedundanciesRequest):
        raise TypeError("Redundancy execution requires a FindRedundanciesRequest.")
    if operation not in ("find-redundancies", "dedun"):
        raise ValueError(f"Unsupported redundancy operation: {operation!r}.")
    current_name = store.current_context_name()
    if operation == "dedun" and request.include_descendants:
        access = resolve_existing_context_access(
            store, request.context_name, current_name=current_name
        ).value
        analysis, receipt = run_recursive_dedup(
            store, access.context_name, provider_factory, on_progress=on_progress
        )
        return RedundancyRunResult(analysis, receipt)
    source = prepare_find_redundancies(store, request, current_name=current_name)
    if on_progress is not None:
        on_progress("analyzing", source)
    analysis = analyze_find_redundancies(source, provider_factory)
    if on_progress is not None:
        on_progress("analyzed", source)
    if operation == "find-redundancies":
        return RedundancyRunResult(analysis)
    frame = analysis.contexts[0]
    applicable = tuple(
        (
            handoff
            for handoff in frame.handoffs
            if handoff.classification in DEDUN_ELIGIBLE_RELATIONS
        )
    )
    if not applicable:
        return RedundancyRunResult(analysis)
    port = MemoryStoreDedunPort(store, current_name=current_name)
    plan = prepare_dedun(DedunRequest(applicable), port=port)
    receipt = apply_dedun(plan, recommended_dedun_selections(plan), port=port)
    return RedundancyRunResult(analysis, receipt)
