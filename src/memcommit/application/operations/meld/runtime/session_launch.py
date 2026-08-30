"""Meld Start and Restart preparation through the initial reviewed session."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.application.capabilities.authority.source_use_policy import (
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.application.operations.compare.ledger.execution import (
    connect_comparison_provider,
    ensure_comparison_analysis,
    install_prepared_comparison_analysis,
)
from memcommit.application.operations.compare.ledger.granted_store import (
    load_granted_comparison_artifact,
    recursive_comparison_projection,
)
from memcommit.application.operations.compare.ledger.model import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    ComparisonInput,
)
from memcommit.application.operations.compare.ledger.provider import analyze_comparison
from memcommit.application.operations.compare.ledger.store import (
    load_comparison_analysis,
)
from memcommit.application.operations.meld.model import (
    MeldSession,
    inline_meld_context,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.restart_application import (
    MeldRestartError,
    MeldRestartPort,
    MeldRestartRequest,
    MeldRestartResult,
    run_meld_restart,
)
from memcommit.application.operations.meld.start_application import (
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
from memcommit.study_scenarios.legacy.prewarm.compare import (
    EquivalentComparePrewarmMatch,
    find_declared_equivalent_compare_analysis,
    find_declared_projected_compare_analysis,
    record_equivalent_compare_prewarm,
    record_exact_compare_prewarm,
    record_projected_compare_prewarm,
)
from memcommit.study_scenarios.legacy.prewarm.meld_directional import (
    DirectionalMeldPrewarmMatch,
    find_installed_directional_meld_prewarm,
    find_installed_equivalent_directional_comparison,
)

from .apply import validate_owner_aware_grant_permissions
from .session_review import execute_meld_assessment, prepare_meld_assessment
from .source_bindings import (
    assert_meld_source_bindings,
    assert_unapplied_meld_target,
    load_bound_meld_contexts,
    load_meld_source,
)


class _LiveComparisonRequired(RuntimeError):
    """Internal signal that a prepared symmetric Start needs its provider."""


def _start_comparison(
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
) -> ComparisonAnalysis | None:
    """Resolve the ordered Compare basis at the application boundary.

    Directional Meld may proceed without a Compare basis, but it still reuses
    an exact, equivalent, or safely projected installed basis when one exists.
    Symmetric Meld always materializes a durable exact basis, connecting the
    provider only after every reusable route misses.
    """

    if request.incoming_memory is not None or request.baseline_memory is not None:
        return None
    analysis = request.comparison
    include_descendants = (
        request.left_descendants,
        request.right_descendants,
    )
    if analysis is not None:
        if (
            not analysis.matches(left, right)
            or analysis.include_descendants != include_descendants
            or analysis.ruleset_version != COMPARISON_RULESET_VERSION
        ):
            raise error_type("The supplied ordered Compare analysis is stale.")
        return analysis

    if request.mode == "DIRECTIONAL":
        analysis = load_comparison_analysis(
            left.uid,
            right.uid,
            store=store,
        )
        if analysis is None:
            artifact = load_granted_comparison_artifact(store, left.uid, right.uid)
            analysis = artifact.analysis if artifact is not None else None
        if analysis is not None:
            if (
                not analysis.matches(left, right)
                or analysis.include_descendants != include_descendants
                or analysis.ruleset_version != COMPARISON_RULESET_VERSION
            ):
                raise error_type("The saved ordered Compare analysis is stale.")
            return analysis

        comparison_input = ComparisonInput.from_contexts(
            left,
            right,
            reference_descendants=request.left_descendants,
            compared_descendants=request.right_descendants,
        )
        equivalent = find_installed_equivalent_directional_comparison(
            store=store,
            comparison_input=comparison_input,
            registry_snapshot=load_profile_registry(),
        )
        if equivalent is None:
            return None
        installed = install_prepared_comparison_analysis(
            store=store,
            reference_access=left_access,
            compared_access=right_access,
            reference=left,
            compared=right,
            current_name=current_name,
            include_descendants=include_descendants,
            analysis=equivalent.analysis,
        )
        recorder = (
            record_projected_compare_prewarm
            if equivalent.origin == "PROJECTED_PREWARM"
            else record_equivalent_compare_prewarm
        )
        recorder(
            store,
            entry_key=equivalent.entry_key,
            analysis=installed.analysis,
            prepared_context_names=equivalent.prepared_context_names,
        )
        return installed.analysis

    equivalent_match: EquivalentComparePrewarmMatch | None = None

    def equivalent(comparison_input: ComparisonInput) -> ComparisonAnalysis | None:
        nonlocal equivalent_match
        equivalent_match = find_declared_equivalent_compare_analysis(
            store=store,
            comparison_input=comparison_input,
            current_name=current_name,
            registry_snapshot=load_profile_registry(),
        )
        if equivalent_match is None:
            equivalent_match = find_declared_projected_compare_analysis(
                store=store,
                comparison_input=comparison_input,
                current_name=current_name,
                registry_snapshot=load_profile_registry(),
            )
        return equivalent_match.analysis if equivalent_match is not None else None

    def analyze_live(comparison_input: ComparisonInput) -> ComparisonAnalysis:
        if not allow_provider:
            raise _LiveComparisonRequired
        return analyze_comparison(
            comparison_input,
            connect_comparison_provider(provider_factory),
        )

    try:
        execution = ensure_comparison_analysis(
            store=store,
            reference_access=left_access,
            compared_access=right_access,
            reference=left,
            compared=right,
            current_name=current_name,
            include_descendants=include_descendants,
            require_durable=True,
            analyze=analyze_live,
            equivalent=equivalent,
        )
    except _LiveComparisonRequired:
        return None
    if execution.origin == "EQUIVALENT_SCOPE_PREWARM" and equivalent_match:
        if equivalent_match.origin == "EXACT_PREWARM":
            record_exact_compare_prewarm(
                store,
                entry_key=equivalent_match.entry_key,
                analysis=execution.analysis,
            )
        else:
            recorder = (
                record_projected_compare_prewarm
                if equivalent_match.origin == "PROJECTED_PREWARM"
                else record_equivalent_compare_prewarm
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
    comparison: ComparisonAnalysis | None
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
        provisional_session = MeldSession.create_directional_from_memory(
            request.incoming_text,
            right,
            baseline_descendants=request.right_descendants,
            baseline_memory_selector=request.baseline_memory,
        )
        left = inline_meld_context(provisional_session)
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

    comparison = (
        None
        if inline
        else _start_comparison(
            request,
            store=store,
            left_access=left_access,
            right_access=right_access,
            left=recursive_comparison_projection(left),
            right=recursive_comparison_projection(right),
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
        if provisional_session is None:
            provisional_session = (
                MeldSession.create_directional(
                    left,
                    right,
                    incoming_descendants=request.left_descendants,
                    baseline_descendants=request.right_descendants,
                    granted_incoming=granted_incoming,
                    granted_target=granted_target,
                    incoming_memory_selector=request.incoming_memory,
                    baseline_memory_selector=request.baseline_memory,
                )
                if comparison is None
                else MeldSession.create_directional_from_comparison(
                    comparison,
                    left,
                    right,
                    granted_incoming=granted_incoming,
                    granted_target=granted_target,
                )
            )
        provisional_session.start_initial_analysis()
        if not inline:
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
        comparison=comparison,
        provisional_session=provisional_session,
        directional_prewarm=directional_prewarm,
        provider_required=(
            comparison is None
            if request.mode == "SYMMETRIC"
            else directional_prewarm is None
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
    comparison = prepared.comparison
    if request.mode == "SYMMETRIC" and comparison is None:
        assert prepared.left_access is not None
        comparison_input = ComparisonInput.from_contexts(
            recursive_comparison_projection(prepared.left),
            recursive_comparison_projection(prepared.right),
            reference_descendants=request.left_descendants,
            compared_descendants=request.right_descendants,
        )
        live_analysis = analyze_comparison(
            comparison_input,
            connect_comparison_provider(provider_factory),
        )
        comparison = install_prepared_comparison_analysis(
            store=store,
            reference_access=prepared.left_access,
            compared_access=prepared.right_access,
            reference=recursive_comparison_projection(prepared.left),
            compared=recursive_comparison_projection(prepared.right),
            current_name=prepared.current_name,
            include_descendants=(
                request.left_descendants,
                request.right_descendants,
            ),
            analysis=live_analysis,
        ).analysis

    if request.mode == "DIRECTIONAL":
        assert prepared.provisional_session is not None
        if prepared.directional_prewarm is None:
            frozen, assessment_port = prepare_meld_assessment(
                prepared.provisional_session,
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
            session = prepared.directional_prewarm.session
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
            origin = prepared.directional_prewarm.origin
    else:
        assert comparison is not None
        session = MeldSession.create_symmetric_from_comparison(
            comparison,
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
        origin = "SAVED_COMPARISON"
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
