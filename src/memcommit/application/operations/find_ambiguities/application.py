"""Application boundary for the read-only ``find-ambiguities`` operation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.application.capabilities.reviewing.memory_issue.finding.detection import (
    find_ambiguities as detect_ambiguities,
)
from memcommit.application.capabilities.reviewing.memory_issue.finding.model import (
    AmbiguityReport,
    FindingsProvider,
)
from memcommit.application.capabilities.reviewing.memory_issue.finding.source import (
    QualityFindSourceFrame,
    freeze_quality_find_source,
)
from memcommit.application.capabilities.reviewing.memory_issue.resolution.workbench import (
    QualityFindWorkbenchSession,
    create_quality_find_workbench,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class FindAmbiguitiesRequest:
    """One exact Context or the complete readable Profile namespace."""

    context_name: str | None = None
    all_readable: bool = False

    def __post_init__(self) -> None:
        if type(self.all_readable) is not bool:
            raise TypeError("Find Ambiguities all-readable mode must be boolean.")
        if self.all_readable and self.context_name is not None:
            raise ValueError(
                "Find Ambiguities cannot combine an explicit Context with "
                "all readable Contexts."
            )


@dataclass(frozen=True)
class FindAmbiguitiesResult:
    source: QualityFindSourceFrame
    report: AmbiguityReport
    session: QualityFindWorkbenchSession


def analyze_find_ambiguities(
    source: QualityFindSourceFrame,
    provider_factory: Callable[[], FindingsProvider],
) -> FindAmbiguitiesResult:
    """Run one ambiguity detector against an already frozen Source."""

    report = detect_ambiguities(
        source.analysis_context(),
        provider_factory,
        context_name_by_uid=source.memory_context_names,
    )
    return FindAmbiguitiesResult(
        source=source,
        report=report,
        session=create_quality_find_workbench("ambiguities", source, report),
    )


def prepare_find_ambiguities(
    store: MemoryStore,
    request: FindAmbiguitiesRequest,
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
) -> QualityFindSourceFrame:
    """Resolve authority and freeze the approved ambiguity Source."""

    return freeze_quality_find_source(
        store,
        request.context_name,
        current_name=current_name,
        all_readable=request.all_readable,
        registry=registry,
    )


def find_ambiguities(
    store: MemoryStore,
    request: FindAmbiguitiesRequest,
    provider_factory: Callable[[], FindingsProvider],
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
) -> FindAmbiguitiesResult:
    """Resolve authority, freeze Source, and execute Find Ambiguities."""

    source = prepare_find_ambiguities(
        store,
        request,
        current_name=current_name,
        registry=registry,
    )
    return analyze_find_ambiguities(source, provider_factory)


__all__ = [
    "FindAmbiguitiesRequest",
    "FindAmbiguitiesResult",
    "analyze_find_ambiguities",
    "find_ambiguities",
    "prepare_find_ambiguities",
]
