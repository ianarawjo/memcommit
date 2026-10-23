"""Shared execution boundary for exact ordered peer-relation analyses."""

from __future__ import annotations


from collections.abc import Callable
from dataclasses import dataclass

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    AnalysisRetention,
    MemoryRelationAnalysis,
    MemoryRelationError,
    MemoryRelationInput,
    memory_relation_canonical_digest,
    memory_relation_analysis_matches_input,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository import (
    ConcurrentMemoryRelationUpdateError,
    load_memory_relation_analysis,
    save_memory_relation_analysis,
)
from memcommit.application.context_access.access import ContextAccess
from memcommit.models.context import Context
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.evidence import (
    project_memory_relation_context as _project_memory_relation_context,
)
from memcommit.application.capabilities.context_scope_loading import (
    load_context_and_descendants,
)
from memcommit.providers.policy import (
    COMPARE_LEDGER_PROVIDER_POLICY,
)
from memcommit.providers.clients.codex import CodexChatGPTProvider
from memcommit.persistence.store import MemoryStore


MEMORY_RELATION_AGGREGATE_TIMEOUT_SECONDS = int(
    COMPARE_LEDGER_PROVIDER_POLICY.timeout_floor_seconds or 900
)


@dataclass(frozen=True)
class MemoryRelationExecutionResult:
    """One saved or newly analyzed ordered relation ledger."""

    analysis: MemoryRelationAnalysis
    reused: bool
    durable: bool
    retention: AnalysisRetention | None
    origin: str


def connect_memory_relation_provider(provider_factory):
    """Connect one provider with the whole-ledger timeout boundary."""

    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        provider.timeout = max(
            provider.timeout,
            MEMORY_RELATION_AGGREGATE_TIMEOUT_SECONDS,
        )
    return provider


def project_memory_relation_context(contexts: tuple[Context, ...]) -> Context:
    """Project loaded Contexts through the capability-owned evidence model."""

    return _project_memory_relation_context(contexts)


def load_memory_relation_context(
    access: ContextAccess,
    *,
    include_descendants: bool = False,
) -> Context:
    """Load local Memories with exact owner provenance for relation analysis."""

    reader = access.store
    contexts = (
        load_context_and_descendants(reader, access.context_name)
        if include_descendants
        else (reader.load(access.context_name),)
    )
    return project_memory_relation_context(contexts)


def ensure_memory_relation_analysis(
    *,
    store: MemoryStore,
    reference_access: ContextAccess,
    compared_access: ContextAccess,
    reference: Context,
    compared: Context,
    current_name: str | None,
    include_descendants: tuple[bool, bool] = (False, False),
    memory_selectors: tuple[str | None, str | None] = (None, None),
    refresh: bool = False,
    expected_version: str | None = None,
    require_durable: bool = False,
    analyze: Callable[[MemoryRelationInput], MemoryRelationAnalysis],
) -> MemoryRelationExecutionResult:
    """Reuse or publish the exact ordered basis with source freshness and artifact CAS."""

    comparison_input = MemoryRelationInput.from_contexts(
        reference,
        compared,
        reference_descendants=include_descendants[0],
        compared_descendants=include_descendants[1],
        reference_memory_selector=memory_selectors[0],
        compared_memory_selector=memory_selectors[1],
    )
    existing = load_memory_relation_analysis(
        reference.uid,
        compared.uid,
        store=store,
    )
    if expected_version is not None:
        if (
            not isinstance(expected_version, str)
            or len(expected_version) != 64
            or any(
                character not in "0123456789abcdef" for character in expected_version
            )
        ):
            raise MemoryRelationError(
                "Compare refresh requires a valid opaque saved version."
            )
        if (
            existing is None
            or memory_relation_canonical_digest(existing.to_dict()) != expected_version
        ):
            # This check intentionally precedes provider inference.
            # An external refresh is an action on a reviewed artifact, not an
            # instruction to replace whichever pair revision is latest.
            raise ConcurrentMemoryRelationUpdateError(
                "The saved comparison changed after this refresh was reviewed."
            )
    existing_version = (
        memory_relation_canonical_digest(existing.to_dict())
        if existing is not None
        else None
    )
    # One current ruleset serves this prototype. Reuse is bound to the frozen
    # sources and authority; editing a prompt does not invalidate a saved result.
    if (
        existing is not None
        and memory_relation_analysis_matches_input(existing, comparison_input)
        and existing.matches(reference, compared)
        and not refresh
    ):
        return MemoryRelationExecutionResult(
            analysis=existing,
            reused=True,
            durable=True,
            retention=None,
            origin="SAVED_REUSE",
        )

    analysis = analyze(comparison_input)
    if not memory_relation_analysis_matches_input(analysis, comparison_input):
        raise MemoryRelationError(
            "Compare analysis does not match the requested Memory scope."
        )

    save_memory_relation_analysis(
        store,
        analysis,
        expected_analysis_uid=(existing.uid if existing is not None else None),
        expected_analysis_version=existing_version,
    )
    return MemoryRelationExecutionResult(
        analysis=analysis,
        reused=False,
        durable=True,
        retention=None,
        origin="LIVE",
    )


# Persisted Compare artifacts keep their established schema and storage keys;
# old imports remain aliases while capability-neutral names own production.
ComparisonExecutionResult = MemoryRelationExecutionResult
COMPARISON_AGGREGATE_TIMEOUT_SECONDS = MEMORY_RELATION_AGGREGATE_TIMEOUT_SECONDS
connect_comparison_provider = connect_memory_relation_provider
recursive_comparison_projection = project_memory_relation_context
load_comparison_context = load_memory_relation_context
ensure_comparison_analysis = ensure_memory_relation_analysis
