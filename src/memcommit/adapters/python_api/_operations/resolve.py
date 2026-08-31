"""Operation assembly for public Resolve analysis and exact Apply."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api._support.semantic import safe_semantic_provider
from memcommit.adapters.python_api.errors import (
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.adapters.python_api.resolve import (
    ResolveAnalysisResult,
    ResolveApplyResult,
    ResolveCandidateResult,
    ResolveEffectResult,
    ResolveIssueResult,
)
from memcommit.application.operations.fit.judgment import FitJudgmentError
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.subscription import QueryProviderError
from memcommit.application.operations.resolve.application import (
    ResolveAnalysis,
    ResolveAuthorityError,
    ResolveConflictError,
    ResolveError,
    ResolveFitTarget,
    ResolveRequest,
    apply_resolve as apply_core_resolve,
    run_resolve,
)
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
)
from memcommit.application.operations.resolve.finding_handoff import (
    conflict_handoff_to_resolve_request,
)
from memcommit.application.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.application.operations.resolve.semantic import (
    ProviderResolveSemanticPort,
)
from memcommit.persistence.store import ConcurrentContextUpdateError


def _port(runtime: ClientRuntime) -> MemoryStoreResolvePort:
    try:
        current_name = runtime.store.current_context_name()
    except (FileNotFoundError, OSError, ValueError) as error:
        raise_public(SemanticStorageError, error)
    registry = None
    allow_grants = False
    if runtime.registry is not None:
        try:
            live_registry = load_profile_registry()
            allow_grants = bool(
                runtime.profile is not None
                and runtime.profile.uid == live_registry.active.uid
                and runtime.store_root
                == profile_store_dir(live_registry.active).resolve()
            )
            if allow_grants:
                registry = live_registry
        except (ProfileConfigError, ProfileError) as error:
            raise_public(SemanticAuthorityError, error)
        except OSError as error:
            raise_public(SemanticStorageError, error)
    return MemoryStoreResolvePort(
        runtime.store,
        current_name=current_name,
        registry=registry,
        allow_grants=allow_grants,
    )


def _public(analysis: ResolveAnalysis) -> ResolveAnalysisResult:
    return ResolveAnalysisResult(
        context_name=analysis.frame.display_name,
        context_uid=analysis.frame.context_uid,
        revision=analysis.frame.revision,
        status=analysis.status,
        initial_fit=(
            analysis.initial_fit.verdict if analysis.initial_fit is not None else None
        ),
        initial_fit_reason=(
            analysis.initial_fit.reason if analysis.initial_fit is not None else None
        ),
        question=analysis.question,
        target_fit=analysis.frame.request.target_fit,
        requested_effects=tuple(analysis.frame.request.requested_effects),
        allowed_effects=tuple(analysis.frame.allowed_effects),
        denied_effects=tuple(analysis.frame.denied_effects),
        candidates=tuple(
            ResolveCandidateResult(
                uid=candidate.uid,
                summary=candidate.summary,
                classification=candidate.classification,
                resolution_level=candidate.resolution_level,
                rule_ids=candidate.rule_ids,
                issues=tuple(
                    ResolveIssueResult(
                        uid=issue.uid,
                        kind=issue.kind,
                        memory_uids=issue.memory_uids,
                        selected_interpretation=issue.selected_interpretation,
                        basis_memory_uids=issue.basis_memory_uids,
                        assumptions=issue.assumptions,
                        reason=issue.reason,
                    )
                    for issue in candidate.issues
                ),
                effects=tuple(
                    ResolveEffectResult(
                        kind=effect.kind,
                        memory_uid=effect.memory_uid,
                        before=effect.old_content,
                        after=effect.new_content,
                        source_memory_uids=effect.source_memory_uids,
                        reason=effect.reason,
                    )
                    for effect in candidate.effects
                ),
                grounded=candidate.grounded,
                verification_reason=candidate.verification_reason,
                fit_verdict=candidate.fit.verdict,
                fit_reason=candidate.fit.reason,
                deletes=candidate.cost.deletes,
                creates=candidate.cost.creates,
                updates=candidate.cost.updates,
                changed_units=candidate.cost.changed_units,
            )
            for candidate in analysis.candidates
        ),
        _application_analysis=analysis,
    )


def resolve_context(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    memory_selectors: Sequence[str] = (),
    allow_create: bool = True,
    allow_delete: bool = False,
    guidance: str = "",
    target_fit: ResolveFitTarget = "MAY",
    expected_revision: str | None = None,
) -> ResolveAnalysisResult:
    """Generate and verify one automatic full-frame interpretation plan."""

    try:
        if isinstance(memory_selectors, (str, bytes)):
            raise TypeError("Resolve Memory selectors must be a sequence of uids.")
        request = ResolveRequest(
            context_name=context_name,
            memory_selectors=tuple(memory_selectors),
            allow_create=allow_create,
            allow_delete=allow_delete,
            guidance=guidance,
            target_fit=target_fit,
        )
    except (ResolveError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    return _run_request(runtime, request, expected_revision=expected_revision)


def resolve_conflict_finding(
    runtime: ClientRuntime,
    handoff: QualityFindingHandoff,
    *,
    allow_create: bool = True,
    allow_delete: bool = False,
    guidance: str = "",
    target_fit: ResolveFitTarget = "MAY",
    expected_revision: str | None = None,
) -> ResolveAnalysisResult:
    """Resolve one exact conflict receipt through the normal fresh authority frame."""

    try:
        request = conflict_handoff_to_resolve_request(
            handoff,
            allow_create=allow_create,
            allow_delete=allow_delete,
            guidance=guidance,
            target_fit=target_fit,
        )
    except (QualityFindingHandoffError, ResolveError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    return _run_request(runtime, request, expected_revision=expected_revision)


def _run_request(
    runtime: ClientRuntime,
    request: ResolveRequest,
    *,
    expected_revision: str | None,
) -> ResolveAnalysisResult:
    """Execute one already-typed request without dropping its source binding."""

    port = _port(runtime)
    if request.context_name is not None:
        try:
            request = ResolveRequest(
                context_name=resolve_context_locator(
                    request.context_name,
                    current=port.current_name,
                ),
                memory_selectors=request.memory_selectors,
                allow_create=request.allow_create,
                allow_delete=request.allow_delete,
                guidance=request.guidance,
                target_fit=request.target_fit,
                source_precondition=request.source_precondition,
            )
        except (ResolveError, TypeError, ValueError) as error:
            raise_public(SemanticInputError, error)
    try:
        analysis = run_resolve(
            request,
            frame_port=port,
            semantic_port=ProviderResolveSemanticPort(),
            provider_factory=lambda: safe_semantic_provider(runtime),
            expected_revision=expected_revision,
        )
    except ResolveAuthorityError as error:
        raise_public(SemanticAuthorityError, error)
    except ResolveConflictError as error:
        raise_public(SemanticConflictError, error)
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except SemanticProviderFailure:
        raise
    except (FitJudgmentError, ResolveError) as error:
        raise_public(SemanticExecutionError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    return _public(analysis)


def apply_resolve(
    runtime: ClientRuntime,
    analysis: ResolveAnalysisResult,
    *,
    candidate_uid: str,
) -> ResolveApplyResult:
    """Apply one exact candidate from a reviewed public analysis object."""

    if not isinstance(analysis, ResolveAnalysisResult):
        raise SemanticInputError("Resolve Apply requires a ResolveAnalysisResult.")
    if not isinstance(candidate_uid, str) or not candidate_uid:
        raise SemanticInputError("Resolve Apply requires a candidate uid.")
    port = _port(runtime)
    try:
        receipt = apply_core_resolve(
            analysis._application_analysis,
            candidate_uid,
            frame_port=port,
        )
    except ResolveAuthorityError as error:
        raise_public(SemanticAuthorityError, error)
    except (ResolveConflictError, ConcurrentContextUpdateError) as error:
        raise_public(SemanticConflictError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except ResolveError as error:
        raise_public(SemanticInputError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (RuntimeError, ValueError) as error:
        raise_public(SemanticExecutionError, error)
    return ResolveApplyResult(
        context_name=receipt.context_name,
        context_uid=receipt.context_uid,
        revision=receipt.revision,
        candidate_uid=receipt.candidate_uid,
        checkpoint_uid=receipt.checkpoint_uid,
        created_uids=receipt.created_uids,
        updated_uids=receipt.updated_uids,
        deleted_uids=receipt.deleted_uids,
    )


__all__ = ["apply_resolve", "resolve_conflict_finding", "resolve_context"]
