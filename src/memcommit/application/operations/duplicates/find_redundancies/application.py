"""Application boundary for read-only ``find-redundancies`` discovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.capabilities.memory_issue_analysis.relation_analysis import (
    analyze_memory_redundancies,
)
from memcommit.application.capabilities.memory_issue_analysis.model import (
    DuplicateReport,
    FindingsProvider,
)
from memcommit.application.capabilities.memory_issue_analysis.redundancy_scope import (
    RedundancyScopeAnalysis,
    analyze_independent_redundancy_scope,
    freeze_redundancy_scope,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.application.capabilities.memory_issue_analysis.workbench import (
    QualityFindWorkbenchSession,
    create_quality_find_workbench,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class FindRedundanciesRequest:
    context_name: str | None = None
    include_descendants: bool = False

    def __post_init__(self) -> None:
        if type(self.include_descendants) is not bool:
            raise TypeError("Find Redundancies descendant reach must be boolean.")


@dataclass(frozen=True)
class FindRedundanciesFrameResult:
    """One combined non-recursive Source judgment and its review projection."""

    source: QualityFindSourceFrame
    report: DuplicateReport
    session: QualityFindWorkbenchSession


def analyze_combined_find_redundancies(
    source: QualityFindSourceFrame,
    provider_factory: Callable[[], FindingsProvider],
) -> FindRedundanciesFrameResult:
    """Detect DUN evidence across one exact frozen aggregate Source."""

    if source.include_descendants:
        raise ValueError(
            "A recursive redundancy Source must be analyzed as independent Contexts."
        )
    report = analyze_memory_redundancies(
        source.analysis_context(),
        provider_factory,
        context_name_by_uid=source.memory_context_names,
    )
    return FindRedundanciesFrameResult(
        source=source,
        report=report,
        session=create_quality_find_workbench("duplicates", source, report),
    )


def prepare_find_redundancies(
    store: MemoryStore,
    request: FindRedundanciesRequest,
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
) -> QualityFindSourceFrame:
    """Resolve authority and freeze the exact independent Context frames."""

    access = resolve_existing_context_access(
        store,
        request.context_name,
        current_name=current_name,
        required_permission="READ",
        registry=registry,
    ).value
    return freeze_redundancy_scope(
        store,
        access,
        include_descendants=request.include_descendants,
        registry=registry,
    )


def analyze_find_redundancies(
    source: QualityFindSourceFrame,
    provider_factory: Callable[[], FindingsProvider],
) -> RedundancyScopeAnalysis:
    """Detect DUN evidence independently in every frozen direct frame."""

    return analyze_independent_redundancy_scope(
        source,
        provider_factory,
        operation=analyze_memory_redundancies,
    )


def find_redundancies(
    store: MemoryStore,
    request: FindRedundanciesRequest,
    provider_factory: Callable[[], FindingsProvider],
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
) -> RedundancyScopeAnalysis:
    """Resolve authority, freeze Source, and execute Find Redundancies."""

    source = prepare_find_redundancies(
        store,
        request,
        current_name=current_name,
        registry=registry,
    )
    return analyze_find_redundancies(source, provider_factory)


__all__ = [
    "FindRedundanciesRequest",
    "FindRedundanciesFrameResult",
    "analyze_combined_find_redundancies",
    "analyze_find_redundancies",
    "find_redundancies",
    "prepare_find_redundancies",
]
