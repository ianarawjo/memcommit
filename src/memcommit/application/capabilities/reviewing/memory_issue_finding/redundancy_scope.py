"""Independent per-Context analysis for lexical Find Redundancies scopes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.authority.access import (
    ContextAccess,
    GrantedReadStore,
)
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.readable_catalog import ReadableContextCatalog
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.capabilities.authority.derived_policy import (
    authorize_combination,
)
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    ExactDuplicateGroup,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.findings import (
    DuplicateReport,
    FindingsProvider,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.application.capabilities.reviewing.memory_issue_finding.workbench import (
    QualityFindSourceFrame,
    create_quality_find_workbench,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.handoff import (
    QualityFindingHandoff,
    quality_finding_handoffs,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class RedundancyContextAnalysis:
    """One complete direct-Memory DUN judgment with its exact owner frame."""

    context_name: str
    source: QualityFindSourceFrame
    report: DuplicateReport
    handoffs: tuple[QualityFindingHandoff, ...]


@dataclass(frozen=True)
class RedundancyScopeAnalysis:
    """All independent direct judgments in one frozen lexical scope."""

    source: QualityFindSourceFrame
    contexts: tuple[RedundancyContextAnalysis, ...]

    @property
    def handoffs(self) -> tuple[QualityFindingHandoff, ...]:
        return tuple(handoff for frame in self.contexts for handoff in frame.handoffs)

    @property
    def memory_count(self) -> int:
        return sum(frame.report.memory_count for frame in self.contexts)

    @property
    def exact_item_groups(self) -> tuple[ExactDuplicateGroup, ...]:
        return tuple(
            group for frame in self.contexts for group in frame.report.exact_item_groups
        )


def freeze_redundancy_scope(
    active_store: MemoryStore,
    access: ContextAccess,
    *,
    include_descendants: bool,
    registry: ProfileRegistry | None = None,
) -> QualityFindSourceFrame:
    """Freeze one root or readable lexical subtree as independent frames."""

    if (
        not isinstance(active_store, MemoryStore)
        or not isinstance(access, ContextAccess)
        or type(include_descendants) is not bool
    ):
        raise TypeError("Find Redundancies requires Context access and boolean reach.")
    if not include_descendants:
        authorize_combination((access,))
        context = (
            GrantedReadStore(access, registry=registry).load_direct(access.display_name)
            if access.is_granted
            else access.store.load_direct(access.context_name)
        )
        return QualityFindSourceFrame.create(
            (context,),
            context_names=(access.display_name,),
            target_names=(access.display_name,),
            selection_mode="SINGLE",
            include_descendants=False,
        )

    catalog = ReadableContextCatalog(
        active_store,
        access,
        registry=registry,
        include_query_routes=False,
    )
    names = expand_lexical_context_names(
        ContextScope.create((access.display_name,), include_descendants=True),
        catalog.list_context_names(),
    )
    accesses = tuple(catalog.access_for(name) for name in names)
    # Each Context is a separate provider disclosure. A granted sibling needs
    # DERIVE, but the command does not need COMBINE merely to enumerate it.
    for frame_access in accesses:
        authorize_combination((frame_access,))
    return QualityFindSourceFrame.create(
        tuple(catalog.load_direct(name) for name in names),
        context_names=names,
        target_names=(access.display_name,),
        selection_mode="SINGLE",
        include_descendants=True,
    )


def analyze_independent_redundancy_scope(
    source: QualityFindSourceFrame,
    provider_factory: Callable[[], FindingsProvider],
    *,
    operation: Callable[..., DuplicateReport] = ops.find_redundancies,
) -> RedundancyScopeAnalysis:
    """Analyze every frozen Context exactly once without cross-Context edges."""

    if not isinstance(source, QualityFindSourceFrame) or not callable(provider_factory):
        raise TypeError("Recursive Find Redundancies requires a source and provider.")
    analyses: list[RedundancyContextAnalysis] = []
    for context, context_name in zip(
        source.contexts,
        source.context_names,
        strict=True,
    ):
        direct_source = QualityFindSourceFrame.create(
            (context,),
            context_names=(context_name,),
            target_names=(context_name,),
            selection_mode="SINGLE",
            include_descendants=False,
        )
        report = operation(
            context,
            provider_factory,
            context_name_by_uid=direct_source.memory_context_names,
        )
        session = create_quality_find_workbench(
            "duplicates",
            direct_source,
            report,
        )
        analyses.append(
            RedundancyContextAnalysis(
                context_name=context_name,
                source=direct_source,
                report=report,
                handoffs=quality_finding_handoffs(session),
            )
        )
    return RedundancyScopeAnalysis(source=source, contexts=tuple(analyses))


__all__ = [
    "RedundancyContextAnalysis",
    "RedundancyScopeAnalysis",
    "analyze_independent_redundancy_scope",
    "freeze_redundancy_scope",
]
