"""Shared execution boundary for exact ordered peer-relation analyses."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.core.context import Context
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.evidence import (
    project_memory_relation_context as _project_memory_relation_context,
)
from memcommit.application.capabilities.context_scope_loading import load_context_scope
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository import (
    load_granted_memory_relation_artifact,
    save_granted_memory_relation_artifact,
)
from memcommit.application.operations.profile.model import (
    authority_grant_snapshot_lock,
)
from memcommit.providers.policy import (
    COMPARE_LEDGER_PROVIDER_POLICY,
)
from memcommit.providers.subscription import CodexChatGPTProvider
from memcommit.persistence.store import MemoryStore

if TYPE_CHECKING:
    from memcommit.application.operations.profile.config import ProfileRegistry


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


def project_memory_relation_context(root: Context) -> Context:
    """Project one readable Context through the capability-owned evidence model."""

    return _project_memory_relation_context(root)


def load_memory_relation_context(
    access: ContextAccess,
    *,
    include_descendants: bool = False,
    registry: ProfileRegistry | None = None,
) -> Context:
    """Load one local or granted source using the exact relation projection."""

    reader = (
        GrantedReadStore(access, registry=registry)
        if access.is_granted
        else access.store
    )
    context = load_context_scope(
        reader,
        access.access_name if access.is_granted else access.context_name,
        include_descendants=include_descendants,
    )
    return project_memory_relation_context(context)


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
    """Reuse or create the exact ordered basis without changing current state.

    The caller freezes the public endpoint meaning once, then supplies the
    Context projections it intends to analyze. This function owns artifact
    lookup, provider-result publication, grant revalidation, and CAS. A
    symmetric Meld may require durable retention because its target-bound
    session must be reproducible; ordinary Compare may still render an
    explicitly unsaved granted result.
    """

    accesses = (reference_access, compared_access)
    granted = any(access.is_granted for access in accesses)
    bindings = tuple(
        freeze_granted_context_binding(access) if access.is_granted else None
        for access in accesses
    )
    comparison_input = MemoryRelationInput.from_contexts(
        reference,
        compared,
        reference_descendants=include_descendants[0],
        compared_descendants=include_descendants[1],
        reference_memory_selector=memory_selectors[0],
        compared_memory_selector=memory_selectors[1],
    )
    granted_artifact = (
        load_granted_memory_relation_artifact(store, reference.uid, compared.uid)
        if granted
        else None
    )
    if granted:
        existing = granted_artifact.analysis if granted_artifact is not None else None
    else:
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
            retention=(
                granted_artifact.retention if granted_artifact is not None else None
            ),
            origin="SAVED_REUSE",
        )

    analysis = analyze(comparison_input)
    if not memory_relation_analysis_matches_input(analysis, comparison_input):
        raise MemoryRelationError(
            "Compare analysis does not match the requested Memory scope."
        )
    if granted:
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
            current_reference = load_memory_relation_context(
                current_accesses[0],
                include_descendants=include_descendants[0],
            )
            current_compared = load_memory_relation_context(
                current_accesses[1],
                include_descendants=include_descendants[1],
            )
            if not analysis.matches(current_reference, current_compared):
                raise ConcurrentMemoryRelationUpdateError(
                    "A granted comparison source changed while Compare was "
                    "analyzing it; no result was published."
                )
            current_retention: AnalysisRetention = "RETAINED"
            save_granted_memory_relation_artifact(
                store,
                analysis,
                current_accesses,
                retention=current_retention,
                expected_analysis_uid=(existing.uid if existing is not None else None),
                expected_analysis_version=existing_version,
            )
        return MemoryRelationExecutionResult(
            analysis=analysis,
            reused=False,
            durable=current_retention is not None,
            retention=current_retention,
            origin="LIVE",
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
