"""Application boundary for the read-only ``find-conflicts`` operation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.application.capabilities.reviewing.memory_issue.finding.detection import (
    find_conflicts as detect_conflicts,
)
from memcommit.application.capabilities.reviewing.memory_issue.finding.model import (
    ConflictReport,
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
class FindConflictsRequest:
    """One exact Context or the complete readable Profile namespace."""

    context_name: str | None = None
    all_readable: bool = False

    def __post_init__(self) -> None:
        if type(self.all_readable) is not bool:
            raise TypeError("Find Conflicts all-readable mode must be boolean.")
        if self.all_readable and self.context_name is not None:
            raise ValueError(
                "Find Conflicts cannot combine an explicit Context with "
                "all readable Contexts."
            )


@dataclass(frozen=True)
class FindConflictsResult:
    source: QualityFindSourceFrame
    report: ConflictReport
    session: QualityFindWorkbenchSession


def analyze_find_conflicts(
    source: QualityFindSourceFrame,
    provider_factory: Callable[[], FindingsProvider],
) -> FindConflictsResult:
    """Run one conflict detector against an already frozen Source."""

    report = detect_conflicts(
        source.analysis_context(),
        provider_factory,
        context_name_by_uid=source.memory_context_names,
    )
    return FindConflictsResult(
        source=source,
        report=report,
        session=create_quality_find_workbench("conflicts", source, report),
    )


def prepare_find_conflicts(
    store: MemoryStore,
    request: FindConflictsRequest,
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
) -> QualityFindSourceFrame:
    """Resolve authority and freeze the approved conflict Source."""

    return freeze_quality_find_source(
        store,
        request.context_name,
        current_name=current_name,
        all_readable=request.all_readable,
        registry=registry,
    )


def find_conflicts(
    store: MemoryStore,
    request: FindConflictsRequest,
    provider_factory: Callable[[], FindingsProvider],
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
) -> FindConflictsResult:
    """Resolve authority, freeze Source, and execute Find Conflicts."""

    source = prepare_find_conflicts(
        store,
        request,
        current_name=current_name,
        registry=registry,
    )
    return analyze_find_conflicts(source, provider_factory)


__all__ = [
    "FindConflictsRequest",
    "FindConflictsResult",
    "analyze_find_conflicts",
    "find_conflicts",
    "prepare_find_conflicts",
]
