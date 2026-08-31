"""Operation-neutral access to legacy Study peer-relation prewarms.

The persisted artifacts, registry operation, and receipt keys remain Compare-
labelled for compatibility. Production consumers use this facade so that those
wire names do not make the Compare operation the Python owner of relation
analysis.
"""

from __future__ import annotations

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    MemoryRelationAnalysis,
    MemoryRelationInput,
)
from memcommit.application.operations.profiles.profile.config import ProfileRegistry
from memcommit.persistence.store import MemoryStore
from memcommit.study_scenarios.legacy.prewarm.compare import (
    EquivalentComparePrewarmMatch,
    find_declared_equivalent_compare_analysis,
    find_declared_projected_compare_analysis,
    installed_compare_prewarm_origin,
    record_equivalent_compare_prewarm,
    record_exact_compare_prewarm,
    record_projected_compare_prewarm,
)
from memcommit.study_scenarios.legacy.prewarm.meld_directional import (
    find_installed_equivalent_directional_comparison,
)


EquivalentMemoryRelationPrewarmMatch = EquivalentComparePrewarmMatch


def find_declared_equivalent_memory_relation_analysis(
    *,
    store: MemoryStore,
    relation_input: MemoryRelationInput,
    current_name: str | None,
    registry_snapshot: ProfileRegistry,
) -> EquivalentMemoryRelationPrewarmMatch | None:
    return find_declared_equivalent_compare_analysis(
        store=store,
        comparison_input=relation_input,
        current_name=current_name,
        registry_snapshot=registry_snapshot,
    )


def find_declared_projected_memory_relation_analysis(
    *,
    store: MemoryStore,
    relation_input: MemoryRelationInput,
    current_name: str | None,
    registry_snapshot: ProfileRegistry,
) -> EquivalentMemoryRelationPrewarmMatch | None:
    return find_declared_projected_compare_analysis(
        store=store,
        comparison_input=relation_input,
        current_name=current_name,
        registry_snapshot=registry_snapshot,
    )


def find_installed_equivalent_directional_relation_analysis(
    *,
    store: MemoryStore,
    relation_input: MemoryRelationInput,
    registry_snapshot: ProfileRegistry | None = None,
) -> EquivalentMemoryRelationPrewarmMatch | None:
    return find_installed_equivalent_directional_comparison(
        store=store,
        comparison_input=relation_input,
        registry_snapshot=registry_snapshot,
    )


def record_exact_memory_relation_prewarm(
    store: MemoryStore,
    *,
    entry_key: str,
    analysis: MemoryRelationAnalysis,
) -> None:
    record_exact_compare_prewarm(store, entry_key=entry_key, analysis=analysis)


def record_equivalent_memory_relation_prewarm(
    store: MemoryStore,
    *,
    entry_key: str,
    analysis: MemoryRelationAnalysis,
    prepared_context_names: tuple[str, str],
) -> None:
    record_equivalent_compare_prewarm(
        store,
        entry_key=entry_key,
        analysis=analysis,
        prepared_context_names=prepared_context_names,
    )


def record_projected_memory_relation_prewarm(
    store: MemoryStore,
    *,
    entry_key: str,
    analysis: MemoryRelationAnalysis,
    prepared_context_names: tuple[str, str],
) -> None:
    record_projected_compare_prewarm(
        store,
        entry_key=entry_key,
        analysis=analysis,
        prepared_context_names=prepared_context_names,
    )


def installed_memory_relation_prewarm_origin(
    store: MemoryStore,
    analysis: MemoryRelationAnalysis,
) -> str | None:
    return installed_compare_prewarm_origin(store, analysis)


__all__ = [
    "EquivalentMemoryRelationPrewarmMatch",
    "find_declared_equivalent_memory_relation_analysis",
    "find_declared_projected_memory_relation_analysis",
    "find_installed_equivalent_directional_relation_analysis",
    "installed_memory_relation_prewarm_origin",
    "record_equivalent_memory_relation_prewarm",
    "record_exact_memory_relation_prewarm",
    "record_projected_memory_relation_prewarm",
]
