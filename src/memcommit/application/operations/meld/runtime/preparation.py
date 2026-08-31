"""MemoryStore-backed preparation for new and replacement Meld pipelines."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.application.authorization.source_use import (
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.execution import (
    connect_memory_relation_provider,
    ensure_memory_relation_analysis,
    install_prepared_memory_relation_analysis,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.granted_repository import (
    project_memory_relation_context,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    MEMORY_RELATION_RULESET_VERSION,
    MemoryRelationAnalysis,
    MemoryRelationInput,
)
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract import (
    analyze_memory_relations,
)
from memcommit.application.operations.meld.model import (
    MeldSession,
    inline_meld_context,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.preparation import (
    MeldRestartError,
    MeldRestartPort,
    MeldRestartRequest,
    MeldRestartResult,
    run_meld_restart,
)
from memcommit.application.operations.meld.preparation import (
    MeldStartError,
    MeldStartOrigin,
    MeldStartPort,
    MeldStartRequest,
    MeldStartResult,
    run_meld_start,
)
from memcommit.application.operations.profile.config import load_profile_registry
from memcommit.application.operations.profile.model import (
    authority_grant_snapshot_lock,
)
from memcommit.core.context import AutoCheckpoint, Context
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
)
from memcommit.study_scenarios.legacy.prewarm.meld_directional import (
    DirectionalMeldPrewarmMatch,
    find_installed_directional_meld_prewarm,
)
from memcommit.study_scenarios.legacy.prewarm.peer_relations import (
    EquivalentMemoryRelationPrewarmMatch,
    find_declared_equivalent_memory_relation_analysis,
    find_declared_projected_memory_relation_analysis,
    find_installed_equivalent_directional_relation_analysis,
    record_equivalent_memory_relation_prewarm,
    record_exact_memory_relation_prewarm,
    record_projected_memory_relation_prewarm,
)

from .apply_transaction import validate_owner_aware_grant_permissions
from .proposal_iteration import execute_meld_assessment, prepare_meld_assessment
from .source_access import (
    assert_meld_source_bindings,
    assert_unapplied_meld_target,
    load_bound_meld_contexts,
    load_meld_source,
)


class _LiveRelationAnalysisRequired(RuntimeError):
    """Internal signal that a prepared Meld Start needs relation analysis."""


def _start_relation_analysis(
    request: MeldStartRequest | MeldRestartRequest,
    *,
    store: MemoryStore,
    left_access: ContextAccess,
    right_access: ContextAccess,
    left: Context,
    right: Context,
    current_name: str | None,
    provider_factory,
    allow_provider: bool = True,
    error_type: type[RuntimeError] = MeldStartError,
) -> MemoryRelationAnalysis | None:
    """Resolve the ordered peer-relation analysis at the Meld boundary.

    Every Meld first fixes one relation ledger. Context sources retain it as a
    durable peer-relation artifact; process-local inline input retains it only
    inside the target-bound session. Meld may choose different materialization
    policies, but it must not silently become a second relation-classification
    engine when reuse misses.
    """

    analysis = request.relation_analysis
    include_descendants = (
        request.left_descendants,
        request.right_descendants,
    )
    if analysis is not None:
        if (
            not analysis.matches(left, right)
            or analysis.include_descendants != include_descendants
            or analysis.ruleset_version != MEMORY_RELATION_RULESET_VERSION
        ):
            raise error_type("The supplied peer-relation analysis is stale.")
        return analysis

    equivalent_match: EquivalentMemoryRelationPrewarmMatch | None = None

    def equivalent(
        relation_input: MemoryRelationInput,
    ) -> MemoryRelationAnalysis | None:
        nonlocal equivalent_match
        if request.mode == "DIRECTIONAL":
            equivalent_match = find_installed_equivalent_directional_relation_analysis(
                store=store,
                relation_input=relation_input,
                registry_snapshot=load_profile_registry(),
            )
            if equivalent_match is not None:
                return equivalent_match.analysis
        equivalent_match = find_declared_equivalent_memory_relation_analysis(
            store=store,
            relation_input=relation_input,
            current_name=current_name,
            registry_snapshot=load_profile_registry(),
        )
        if equivalent_match is None:
            equivalent_match = find_declared_projected_memory_relation_analysis(
                store=store,
                relation_input=relation_input,
                current_name=current_name,
                registry_snapshot=load_profile_registry(),
            )
        return equivalent_match.analysis if equivalent_match is not None else None

    def analyze_live(relation_input: MemoryRelationInput) -> MemoryRelationAnalysis:
        if not allow_provider:
            raise _LiveRelationAnalysisRequired
        return analyze_memory_relations(
            relation_input,
            connect_memory_relation_provider(provider_factory),
        )

    try:
        execution = ensure_memory_relation_analysis(
            store=store,
            reference_access=left_access,
            compared_access=right_access,
            reference=left,
            compared=right,
            current_name=current_name,
            include_descendants=include_descendants,
            memory_selectors=(
                request.incoming_memory,
                request.baseline_memory,
            ),
            require_durable=True,
            analyze=analyze_live,
            equivalent=equivalent,
        )
    except _LiveRelationAnalysisRequired:
        return None
    if execution.origin == "EQUIVALENT_SCOPE_PREWARM" and equivalent_match:
        if equivalent_match.origin == "EXACT_PREWARM":
            record_exact_memory_relation_prewarm(
                store,
                entry_key=equivalent_match.entry_key,
                analysis=execution.analysis,
            )
        else:
            recorder = (
                record_projected_memory_relation_prewarm
                if equivalent_match.origin == "PROJECTED_PREWARM"
                else record_equivalent_memory_relation_prewarm
            )
            recorder(
                store,
                entry_key=equivalent_match.entry_key,
                analysis=execution.analysis,
                prepared_context_names=equivalent_match.prepared_context_names,
            )
    return execution.analysis


@dataclass(frozen=True)
class PreparedMeldExecution:
    """Frozen Start/Restart inputs plus the exact remaining semantic work."""

    request: MeldStartRequest | MeldRestartRequest
    store: MemoryStore
    current_name: str | None
    left_access: ContextAccess | None
    right_access: ContextAccess
    left: Context
    right: Context
    target: Context
    expected_session_digest: str | None
    create_target: bool
    relation_analysis: MemoryRelationAnalysis | None
    provisional_session: MeldSession | None
    directional_prewarm: DirectionalMeldPrewarmMatch | None
    provider_required: bool


def _prepare_initial_meld(
    request: MeldStartRequest | MeldRestartRequest,
    *,
    store: MemoryStore,
    expected_session_digest: str | None,
    create_target: bool,
    error_type: type[RuntimeError],
) -> PreparedMeldExecution:
    """Freeze one Start/Restart and resolve every provider-free cache route."""

    current_name = store.current_context_name()
    inline = request.incoming_text is not None
    left_access = (
        None
        if inline
        else resolve_context_access(
            store,
            request.left_name,
            current_name=current_name,
            required_permission="READ",
        )
    )
    right_access = resolve_context_access(
        store,
        request.right_name,
        current_name=current_name,
        required_permission="READ",
    )
    if left_access is not None:
        authorize_combination((left_access, right_access))

    if request.mode == "DIRECTIONAL":
        if inline:
            if right_access.is_granted:
                raise error_type(
                    "Inline-Memory Meld currently requires a local BASELINE/Target."
                )
        else:
            assert left_access is not None
            authorize_derived_transfer(left_access, right_access)
            retention = analysis_retention((left_access, right_access))
            if retention is None:
                raise error_type(
                    "The directional Meld cannot retain its reviewed analysis."
                )
            authorize_analysis_save(
                (left_access, right_access),
                retention=retention,
            )
        target_access = right_access
    else:
        assert left_access is not None
        if create_target:
            store.assert_context_creatable(request.target_name)
            target_access = ContextAccess(
                store=store,
                context_name=request.target_name,
                display_name=request.target_name,
                attachment_name=None,
                permission="READ",
            )
        else:
            target_access = resolve_context_access(
                store,
                request.target_name,
                current_name=current_name,
                required_permission="READ",
            )
            if target_access.is_granted:
                raise error_type("Symmetric Meld requires a local Result Context.")
        authorize_derived_transfer(left_access, target_access)
        authorize_derived_transfer(right_access, target_access)

    project = request.mode == "SYMMETRIC"
    right = load_meld_source(
        right_access,
        include_descendants=request.right_descendants,
        project=project,
    )
    provisional_session: MeldSession | None = None
    if inline:
        assert request.incoming_text is not None
        inline_session = MeldSession.create_directional_from_memory(
            request.incoming_text,
            right,
            baseline_descendants=request.right_descendants,
            baseline_memory_selector=request.baseline_memory,
        )
        left = inline_meld_context(inline_session)
    else:
        assert left_access is not None
        left = load_meld_source(
            left_access,
            include_descendants=request.left_descendants,
            project=project,
        )

    if request.mode == "DIRECTIONAL":
        target = right
    elif create_target:
        target = Context(uid=str(uuid.uuid4()), name=request.target_name)
    else:
        target = store.load_direct(request.target_name)
        if tuple(target.iter_items()):
            raise error_type("Symmetric Meld Result must remain empty.")

    prior = store.load_meld_session(target.uid)
    if expected_session_digest is None:
        if prior is not None:
            raise error_type("The Meld target already owns a saved session.")
    else:
        if prior is None:
            raise ConcurrentContextUpdateError(
                "The Meld session disappeared before restart."
            )
        if meld_canonical_digest(prior.to_dict()) != expected_session_digest:
            raise ConcurrentContextUpdateError(
                "The Meld session changed before restart."
            )

    relation_analysis = (
        None
        if inline
        else _start_relation_analysis(
            request,
            store=store,
            left_access=left_access,
            right_access=right_access,
            left=project_memory_relation_context(left),
            right=project_memory_relation_context(right),
            current_name=current_name,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("Meld preparation connected a provider.")
            ),
            allow_provider=False,
            error_type=error_type,
        )
    )
    directional_prewarm: DirectionalMeldPrewarmMatch | None = None
    if request.mode == "DIRECTIONAL":
        granted_incoming = (
            freeze_granted_context_binding(left_access)
            if left_access is not None and left_access.is_granted
            else None
        )
        granted_target = (
            freeze_granted_context_binding(right_access)
            if right_access.is_granted
            else None
        )
        if relation_analysis is not None:
            provisional_session = MeldSession.create_directional_from_relation_analysis(
                relation_analysis,
                left,
                right,
                granted_incoming=granted_incoming,
                granted_target=granted_target,
            )
            provisional_session.start_initial_analysis()
            directional_prewarm = find_installed_directional_meld_prewarm(
                store=store,
                current=provisional_session,
            )
    return PreparedMeldExecution(
        request=request,
        store=store,
        current_name=current_name,
        left_access=left_access,
        right_access=right_access,
        left=left,
        right=right,
        target=target,
        expected_session_digest=expected_session_digest,
        create_target=create_target,
        relation_analysis=relation_analysis,
        provisional_session=provisional_session,
        directional_prewarm=directional_prewarm,
        provider_required=(
            relation_analysis is None
            if request.mode == "SYMMETRIC"
            else relation_analysis is None or directional_prewarm is None
        ),
    )


def _execute_prepared_initial_meld(
    prepared: PreparedMeldExecution,
    *,
    provider_factory,
    error_type: type[RuntimeError],
) -> tuple[MeldSession, MeldStartOrigin]:
    """Execute one frozen plan without repeating its provider-free cache search."""

    request = prepared.request
    store = prepared.store
    relation_analysis = prepared.relation_analysis
    if relation_analysis is None:
        relation_input = MemoryRelationInput.from_contexts(
            project_memory_relation_context(prepared.left),
            project_memory_relation_context(prepared.right),
            reference_descendants=request.left_descendants,
            compared_descendants=request.right_descendants,
            reference_memory_selector=request.incoming_memory,
            compared_memory_selector=request.baseline_memory,
        )
        live_analysis = analyze_memory_relations(
            relation_input,
            connect_memory_relation_provider(provider_factory),
        )
        if prepared.left_access is None:
            # Inline input has no readable Context locator or independent
            # artifact slot. Its exact relation ledger is retained inside the
            # target-bound Meld session instead.
            relation_analysis = live_analysis
        else:
            relation_analysis = install_prepared_memory_relation_analysis(
                store=store,
                reference_access=prepared.left_access,
                compared_access=prepared.right_access,
                reference=project_memory_relation_context(prepared.left),
                compared=project_memory_relation_context(prepared.right),
                current_name=prepared.current_name,
                include_descendants=(
                    request.left_descendants,
                    request.right_descendants,
                ),
                memory_selectors=(
                    request.incoming_memory,
                    request.baseline_memory,
                ),
                analysis=live_analysis,
            ).analysis

    if request.mode == "DIRECTIONAL":
        assert relation_analysis is not None
        provisional_session = prepared.provisional_session
        if provisional_session is None:
            provisional_session = MeldSession.create_directional_from_relation_analysis(
                relation_analysis,
                prepared.left,
                prepared.right,
                granted_incoming=(
                    freeze_granted_context_binding(prepared.left_access)
                    if prepared.left_access is not None
                    and prepared.left_access.is_granted
                    else None
                ),
                granted_target=(
                    freeze_granted_context_binding(prepared.right_access)
                    if prepared.right_access.is_granted
                    else None
                ),
            )
            provisional_session.start_initial_analysis()
        directional_prewarm = prepared.directional_prewarm
        if directional_prewarm is None and prepared.provisional_session is None:
            directional_prewarm = find_installed_directional_meld_prewarm(
                store=store,
                current=provisional_session,
            )
        if directional_prewarm is None:
            frozen, assessment_port = prepare_meld_assessment(
                provisional_session,
                store=store,
                expected_session_digest=prepared.expected_session_digest,
            )
            session = execute_meld_assessment(
                frozen,
                port=assessment_port,
                provider_factory=provider_factory,
            ).session
            origin = "PROVIDER"
        else:
            session = directional_prewarm.session
            left_live, right_live, target_live = load_bound_meld_contexts(
                store,
                session,
            )
            assert_meld_source_bindings(session, left_live, right_live)
            assert_unapplied_meld_target(session, target_live)
            if session.granted_target is not None:
                assessment = session.current_assessment
                assert assessment is not None
                with authority_grant_snapshot_lock() as registry:
                    revalidate_granted_context_binding(
                        session.granted_target,
                        registry=registry,
                    )
                    validate_owner_aware_grant_permissions(
                        session,
                        assessment.proposals,
                        registry=registry,
                    )
            store.save_meld_session(
                session,
                expected_session_digest=prepared.expected_session_digest,
            )
            origin = directional_prewarm.origin
    else:
        assert relation_analysis is not None
        session = MeldSession.create_symmetric_from_relation_analysis(
            relation_analysis,
            prepared.target,
        )
        assert_meld_source_bindings(session, prepared.left, prepared.right)
        assert_unapplied_meld_target(session, prepared.target)
        if prepared.create_target:
            store.create_meld_target_with_session(
                prepared.target,
                session,
                AutoCheckpoint(
                    command="meld",
                    args={
                        "left": request.left_name,
                        "right": request.right_name,
                        "to": request.target_name,
                    },
                    description=(
                        f"Initialized symmetric Meld result "
                        f"'{request.target_name}' from "
                        f"'{request.left_name}' and '{request.right_name}'"
                    ),
                ),
            )
        else:
            store.save_meld_session(
                session,
                expected_session_digest=prepared.expected_session_digest,
            )
        origin = "SAVED_RELATION_ANALYSIS"
    return session, origin


def _execute_initial_meld(
    request: MeldStartRequest | MeldRestartRequest,
    *,
    store: MemoryStore,
    provider_factory,
    expected_session_digest: str | None,
    create_target: bool,
    error_type: type[RuntimeError],
) -> tuple[MeldSession, MeldStartOrigin]:
    """Prepare and publish one initial review under a create-or-replace token."""

    prepared = _prepare_initial_meld(
        request,
        store=store,
        expected_session_digest=expected_session_digest,
        create_target=create_target,
        error_type=error_type,
    )
    return _execute_prepared_initial_meld(
        prepared,
        provider_factory=provider_factory,
        error_type=error_type,
    )


@dataclass
class MemoryStoreMeldStartPort(MeldStartPort):
    """Authorize and publish a new target-scoped Meld without interface code."""

    store: MemoryStore
    prepared: PreparedMeldExecution | None = None

    def start(
        self,
        request: MeldStartRequest,
        *,
        provider_factory,
    ) -> MeldStartResult:
        if self.prepared is not None:
            if (
                self.prepared.request != request
                or self.prepared.store is not self.store
            ):
                raise MeldStartError("Prepared Meld Start does not match its request.")
            session, origin = _execute_prepared_initial_meld(
                self.prepared,
                provider_factory=provider_factory,
                error_type=MeldStartError,
            )
        else:
            session, origin = _execute_initial_meld(
                request,
                store=self.store,
                provider_factory=provider_factory,
                expected_session_digest=None,
                create_target=request.create_target,
                error_type=MeldStartError,
            )
        return MeldStartResult(
            session=session,
            origin=origin,
            created_target=request.create_target,
        )


def execute_meld_start(
    request: MeldStartRequest,
    *,
    store: MemoryStore,
    provider_factory,
    prepared: PreparedMeldExecution | None = None,
) -> MeldStartResult:
    """Start one complete Meld through the production Store/Grant adapter."""

    return run_meld_start(
        request,
        port=MemoryStoreMeldStartPort(store, prepared=prepared),
        provider_factory=provider_factory,
    )


def prepare_meld_start(
    request: MeldStartRequest,
    *,
    store: MemoryStore,
) -> PreparedMeldExecution:
    """Freeze a new Meld and report whether its exact plan needs a provider."""

    return _prepare_initial_meld(
        request,
        store=store,
        expected_session_digest=None,
        create_target=request.create_target,
        error_type=MeldStartError,
    )


@dataclass
class MemoryStoreMeldRestartPort(MeldRestartPort):
    """CAS-replace an existing target-scoped Meld without interface code."""

    store: MemoryStore
    prepared: PreparedMeldExecution | None = None

    def restart(
        self,
        request: MeldRestartRequest,
        *,
        provider_factory,
    ) -> MeldRestartResult:
        if self.prepared is not None:
            if (
                self.prepared.request != request
                or self.prepared.store is not self.store
            ):
                raise MeldRestartError(
                    "Prepared Meld Restart does not match its request."
                )
            session, origin = _execute_prepared_initial_meld(
                self.prepared,
                provider_factory=provider_factory,
                error_type=MeldRestartError,
            )
        else:
            session, origin = _execute_initial_meld(
                request,
                store=self.store,
                provider_factory=provider_factory,
                expected_session_digest=request.expected_version,
                create_target=False,
                error_type=MeldRestartError,
            )
        return MeldRestartResult(session=session, origin=origin)


def execute_meld_restart(
    request: MeldRestartRequest,
    *,
    store: MemoryStore,
    provider_factory,
    prepared: PreparedMeldExecution | None = None,
) -> MeldRestartResult:
    """Restart one Meld through the production Store/Grant adapter."""

    return run_meld_restart(
        request,
        port=MemoryStoreMeldRestartPort(store, prepared=prepared),
        provider_factory=provider_factory,
    )


def prepare_meld_restart(
    request: MeldRestartRequest,
    *,
    store: MemoryStore,
) -> PreparedMeldExecution:
    """Freeze a replacement Meld under its exact saved-session version."""

    return _prepare_initial_meld(
        request,
        store=store,
        expected_session_digest=request.expected_version,
        create_target=False,
        error_type=MeldRestartError,
    )
