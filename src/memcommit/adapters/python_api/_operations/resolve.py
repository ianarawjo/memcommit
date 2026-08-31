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
    ResolveDecisionInput,
    ResolveIssueResult,
)
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
    ResolveRequest,
    run_resolve,
)
from memcommit.application.operations.resolve.decisions import (
    ResolveDecision,
    apply_resolve_update,
    plan_resolve_update,
)
from memcommit.application.capabilities.memory_issue_analysis.model import FindingsError
from memcommit.application.operations.update.model import (
    UpdateError,
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
from memcommit.persistence.operations.audit import JsonAuditRecordRepository


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
        question=analysis.question,
        requested_effects=tuple(analysis.frame.request.requested_effects),
        allowed_effects=tuple(analysis.frame.allowed_effects),
        denied_effects=tuple(analysis.frame.denied_effects),
        issues=tuple(
            ResolveIssueResult(
                uid=issue.uid,
                audit_key=issue.audit_key,
                kind=issue.kind,
                classification=issue.classification,
                memory_uids=issue.memory_uids,
                proposed_direction=issue.proposed_direction,
                reason=issue.reason,
                question=issue.question,
            )
            for issue in analysis.review_issues
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
    expected_revision: str | None = None,
) -> ResolveAnalysisResult:
    """Return conflicts and conservative understandings for human decisions."""

    try:
        if isinstance(memory_selectors, (str, bytes)):
            raise TypeError("Resolve Memory selectors must be a sequence of uids.")
        request = ResolveRequest(
            context_name=context_name,
            memory_selectors=tuple(memory_selectors),
            allow_create=allow_create,
            allow_delete=allow_delete,
            guidance=guidance,
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
    expected_revision: str | None = None,
) -> ResolveAnalysisResult:
    """Resolve one exact conflict receipt through the normal fresh authority frame."""

    try:
        request = conflict_handoff_to_resolve_request(
            handoff,
            allow_create=allow_create,
            allow_delete=allow_delete,
            guidance=guidance,
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
                source_precondition=request.source_precondition,
            )
        except (ResolveError, TypeError, ValueError) as error:
            raise_public(SemanticInputError, error)
    try:
        analysis = run_resolve(
            request,
            frame_port=port,
            semantic_port=ProviderResolveSemanticPort(),
            audit_repository=JsonAuditRecordRepository(runtime.store),
            audit_provider_factory=lambda: safe_semantic_provider(runtime),
            direction_provider_factory=lambda: safe_semantic_provider(runtime),
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
    except ResolveError as error:
        raise_public(SemanticExecutionError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    return _public(analysis)


def apply_resolve(
    runtime: ClientRuntime,
    analysis: ResolveAnalysisResult,
    *,
    decisions: Sequence[ResolveDecisionInput],
) -> ResolveApplyResult:
    """Generate and apply one verified UpdatePlan from finalized decisions."""

    if not isinstance(analysis, ResolveAnalysisResult):
        raise SemanticInputError("Resolve Apply requires a ResolveAnalysisResult.")
    if isinstance(decisions, (str, bytes)):
        raise SemanticInputError("Resolve decisions must be a sequence.")
    try:
        core_decisions = tuple(
            ResolveDecision(value.issue_uid, value.kind, value.intent)
            for value in decisions
        )
    except (AttributeError, ResolveError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    port = _port(runtime)
    try:
        proposal = plan_resolve_update(
            analysis._application_analysis,
            core_decisions,
            frame_port=port,
            update_provider_factory=lambda: safe_semantic_provider(runtime),
            audit_provider_factory=lambda: safe_semantic_provider(runtime),
        )
        receipt = apply_resolve_update(proposal, frame_port=port)
    except ResolveAuthorityError as error:
        raise_public(SemanticAuthorityError, error)
    except (ResolveConflictError, ConcurrentContextUpdateError) as error:
        raise_public(SemanticConflictError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except (FindingsError, UpdateError, ResolveError) as error:
        raise_public(SemanticInputError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (RuntimeError, ValueError) as error:
        raise_public(SemanticExecutionError, error)
    return ResolveApplyResult(
        context_name=receipt.context_name,
        context_uid=receipt.context_uid,
        revision=receipt.revision,
        plan_uid=receipt.plan_uid,
        checkpoint_uid=receipt.checkpoint_uid,
        created_uids=receipt.created_uids,
        updated_uids=receipt.updated_uids,
        deleted_uids=receipt.deleted_uids,
        unresolved_issue_uids=receipt.unresolved_issue_uids,
    )


__all__ = ["apply_resolve", "resolve_conflict_finding", "resolve_context"]
