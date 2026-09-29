"""Run Find Redundancies or Dedun through one frozen analysis."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingSource,
)
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
    apply_recursive_dedun_scope,
    freeze_recursive_dedun_scope,
    prepare_recursive_dedun_scope,
)
from memcommit.application.operations.duplicates.find_redundancies.application import (
    FindRedundanciesRequest,
    analyze_find_redundancies,
    prepare_find_redundancies,
)
from memcommit.persistence.store import MemoryStore

RedundancyOperation = Literal["find-redundancies", "dedun"]
RedundancyRunStage = Literal["analyzing", "analyzed"]


@dataclass(frozen=True)
class RedundancyRunResult:
    """The complete analysis and, for an applied Dedun, its durable receipt."""

    analysis: RedundancyScopeAnalysis
    receipt: DedunReceipt | DedunScopeReceipt | None = None


def run_redundancies(
    request: FindRedundanciesRequest,
    *,
    operation: RedundancyOperation,
    store: MemoryStore,
    provider_factory: Callable[[], FindingsProvider],
    on_progress: Callable[[RedundancyRunStage, QualityFindSourceFrame], None]
    | None = None,
) -> RedundancyRunResult:
    """Freeze inputs, analyze once, and apply only an explicitly requested Dedun."""

    if not isinstance(request, FindRedundanciesRequest):
        raise TypeError("Redundancy execution requires a FindRedundanciesRequest.")
    if operation not in ("find-redundancies", "dedun"):
        raise ValueError(f"Unsupported redundancy operation: {operation!r}.")

    # Relative lookup and later Apply must share the same active Context snapshot.
    current_name = store.current_context_name()
    recursive_dedun = None
    if operation == "dedun" and request.include_descendants:
        access = resolve_existing_context_access(
            store,
            request.context_name,
            current_name=current_name,
            required_permission="READ",
        ).value
        recursive_dedun = freeze_recursive_dedun_scope(store, access)
        source = recursive_dedun.source
    else:
        source = prepare_find_redundancies(store, request, current_name=current_name)

    if on_progress is not None:
        on_progress("analyzing", source)
    analysis = analyze_find_redundancies(source, provider_factory)
    if on_progress is not None:
        on_progress("analyzed", source)

    if operation == "find-redundancies":
        return RedundancyRunResult(analysis)

    if recursive_dedun is not None:
        port = MemoryStoreDedunPort(
            store, current_name=current_name, allow_grants=False
        )
        prepared = prepare_recursive_dedun_scope(recursive_dedun, analysis, port=port)
        return RedundancyRunResult(
            analysis, apply_recursive_dedun_scope(store, prepared)
        )

    frame = analysis.contexts[0]
    applicable = tuple(
        handoff
        for handoff in frame.handoffs
        if handoff.classification in DEDUN_ELIGIBLE_RELATIONS
    )
    if not applicable and not frame.report.exact_item_groups:
        return RedundancyRunResult(analysis)

    port = MemoryStoreDedunPort(store, current_name=current_name)
    plan = prepare_dedun(
        DedunRequest(
            applicable,
            exact_source=QualityFindingSource(
                context_uid=frame.source.contexts[0].uid,
                display_name=source.context_names[0],
                direct_memory_digest=source.context_digests[0],
            ),
            exact_source_frame_digest=source.digest,
        ),
        port=port,
    )
    receipt = apply_dedun(plan, recommended_dedun_selections(plan), port=port)
    return RedundancyRunResult(analysis, receipt)
