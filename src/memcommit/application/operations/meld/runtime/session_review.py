"""Saved Meld review persistence, provider assessment, and follow-up turns."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.authority.context_access import (
    revalidate_granted_context_binding,
)
from memcommit.application.operations.meld.application import (
    MeldApplicationError,
)
from memcommit.application.operations.meld.assessment_application import (
    FrozenMeldAssessment,
    MeldAssessmentPort,
    MeldAssessmentResult,
    MeldProviderFactory,
    run_meld_assessment,
)
from memcommit.application.operations.meld.model import (
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MeldSession,
    materialize_preservation_assessment,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.provider.request import (
    meld_turn_request_digest,
)
from memcommit.application.operations.meld.resolution_cache import (
    MeldResolutionBranch,
    configured_meld_cache_identity,
    meld_resolution_cache_key,
)
from memcommit.application.operations.meld.session_application import (
    MeldDestinationPort,
    MeldDestinationRequest,
    MeldPreservationPort,
    MeldSessionRepository,
    MeldSessionSnapshot,
    MeldTurnRequest,
    PendingMeldTurn,
    prepare_meld_turn,
    run_meld_initial_preservation,
    run_meld_destination_change,
    run_meld_preservation,
    run_meld_session_defer,
    run_meld_session_open,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import (
    MemoryStore,
)
from memcommit.providers.subscription import CodexChatGPTProvider
from memcommit.providers.types import ProviderIdentity
from memcommit.study_scenarios.legacy.prewarm.meld_resolution import (
    find_installed_meld_resolution_branch,
)

from .apply import validate_owner_aware_grant_permissions
from .source_bindings import (
    assert_meld_source_bindings,
    assert_unapplied_meld_target,
    load_bound_meld_contexts,
)

MELD_AGGREGATE_TIMEOUT_SECONDS = 900


def connect_meld_provider(provider_factory):
    """Connect one provider under Meld's complete-ledger timeout boundary."""

    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        provider.timeout = max(provider.timeout, MELD_AGGREGATE_TIMEOUT_SECONDS)
    return provider

@dataclass
class MemoryStoreMeldSessionRepository(MeldSessionRepository):
    """Target-scoped Meld persistence with opaque canonical-digest CAS tokens."""

    store: MemoryStore

    @staticmethod
    def _snapshot(session: MeldSession) -> MeldSessionSnapshot:
        return MeldSessionSnapshot(
            session=session,
            version_token=meld_canonical_digest(session.to_dict()),
        )

    def load(self, target_context_uid: str) -> MeldSessionSnapshot:
        session = self.store.load_meld_session(target_context_uid)
        if session is None:
            raise FileNotFoundError(
                f"No saved Meld session for target {target_context_uid!r}."
            )
        return self._snapshot(session)

    def replace(
        self,
        session: MeldSession,
        *,
        expected_version: str,
    ) -> MeldSessionSnapshot:
        self.store.save_meld_session(
            session,
            expected_session_digest=expected_version,
        )
        return self._snapshot(session)


@dataclass
class MemoryStoreMeldPreservationPort(MeldPreservationPort):
    """Revalidate and publish one provider-free symmetric preserve-all turn."""

    store: MemoryStore

    def materialize(
        self,
        snapshot: MeldSessionSnapshot,
        session: MeldSession,
    ) -> MeldSessionSnapshot:
        assessment = materialize_preservation_assessment(session)
        left, right, target = load_bound_meld_contexts(self.store, session)
        assert_meld_source_bindings(session, left, right)
        assert_unapplied_meld_target(session, target)
        current = session.current_turn
        assert current is not None
        session.record_assessment(current.uid, assessment)
        return MemoryStoreMeldSessionRepository(self.store).replace(
            session,
            expected_version=snapshot.version_token,
        )


@dataclass
class MemoryStoreMeldDestinationPort(MeldDestinationPort):
    """Relocate one empty symmetric Result and its target-scoped session."""

    store: MemoryStore

    def relocate(self, request: MeldDestinationRequest) -> MeldSessionSnapshot:
        destination = request.destination_name
        validate_portable_context_name(destination)
        session = request.snapshot.session
        descendants = tuple(
            name
            for name in self.store.list_context_names()
            if name.startswith(session.target.context_name + "/")
        )
        if descendants:
            raise ValueError(
                "A symmetric Meld save location with descendants cannot be moved "
                "from the review workbench."
            )
        current = MemoryStoreMeldSessionRepository(self.store).load(
            session.target.context_uid
        )
        if current.version_token != request.snapshot.version_token:
            raise MeldApplicationError(
                "The Meld session changed before its destination could move."
            )
        plan = self.store.plan_context_rename(
            session.target.context_name,
            destination,
        )
        self.store.rename_contexts(plan)
        relocated = self.store.load_meld_session(session.target.context_uid)
        if relocated is None or relocated.uid != session.uid:
            raise MeldApplicationError(
                "The relocated Meld session could not be reloaded."
            )
        return MemoryStoreMeldSessionRepository._snapshot(relocated)


def execute_meld_session_open(
    target_context_uid: str,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_session_open(
        target_context_uid,
        repository=MemoryStoreMeldSessionRepository(store),
    )


def execute_meld_session_defer(
    snapshot: MeldSessionSnapshot,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_session_defer(
        snapshot,
        repository=MemoryStoreMeldSessionRepository(store),
    )


def execute_meld_initial_preservation(
    snapshot: MeldSessionSnapshot,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_initial_preservation(
        snapshot,
        repository=MemoryStoreMeldSessionRepository(store),
    )


def execute_meld_preservation(
    pending,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_preservation(
        pending,
        port=MemoryStoreMeldPreservationPort(store),
    )


def execute_meld_destination_change(
    request: MeldDestinationRequest,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_destination_change(
        request,
        port=MemoryStoreMeldDestinationPort(store),
    )


@dataclass(frozen=True)
class _MeldAssessmentToken:
    owner: object
    cacheable: bool
    request_digest: str | None
    configured_provider: dict[str, object] | None
    cached_branch: MeldResolutionBranch | None
    branch_from_study_prewarm: bool


class MemoryStoreMeldAssessmentPort(MeldAssessmentPort):
    """Freeze hidden resolution branches and publish one assessed session CAS."""

    def __init__(self, store: MemoryStore):
        self._store = store
        self._owner = object()

    def freeze(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str | None,
    ) -> FrozenMeldAssessment:
        current = session.current_turn
        cacheable = (
            current is not None
            and current.sequence > 0
            and current.scope in {"ALL", "REMAINING"}
        )
        request_digest: str | None = None
        configured_provider: dict[str, object] | None = None
        cached_branch = None
        from_study_prewarm = False
        if cacheable:
            request_digest = meld_turn_request_digest(session)
            configured_provider = configured_meld_cache_identity()
            cache_key = meld_resolution_cache_key(
                request_digest,
                configured_provider,
            )
            cached_branch = self._store.load_meld_resolution_branch(cache_key)
            if cached_branch is None:
                cached_branch = find_installed_meld_resolution_branch(
                    store=self._store,
                    branch_key=cache_key,
                    request_digest=request_digest,
                )
                from_study_prewarm = cached_branch is not None
        return FrozenMeldAssessment(
            session=session,
            expected_session_digest=expected_session_digest,
            cached_completion=(
                cached_branch.completion if cached_branch is not None else None
            ),
            token=_MeldAssessmentToken(
                owner=self._owner,
                cacheable=cacheable,
                request_digest=request_digest,
                configured_provider=configured_provider,
                cached_branch=cached_branch,
                branch_from_study_prewarm=from_study_prewarm,
            ),
        )

    def commit(
        self,
        frozen: FrozenMeldAssessment,
        *,
        session: MeldSession,
        assessment,
        completion: str | None,
        origin_provider: object | None,
    ) -> MeldSession:
        token = frozen.token
        if (
            not isinstance(token, _MeldAssessmentToken)
            or token.owner is not self._owner
        ):
            raise MeldApplicationError(
                "Meld assessment binding belongs to another runtime port."
            )
        left, right, target = load_bound_meld_contexts(self._store, session)
        assert_meld_source_bindings(session, left, right)
        assert_unapplied_meld_target(session, target)
        if session.granted_target is not None:
            if session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION:
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
            else:
                required = {
                    "UPDATE" if proposal.operation == "EDIT" else "CREATE"
                    for proposal in assessment.proposals
                }
                missing = sorted(required - set(session.granted_target.permissions))
                if missing:
                    raise ProfileError(
                        "The BASELINE Grant does not authorize "
                        + " + ".join(missing)
                        + " required by the proposed Meld changes."
                    )
        if token.cacheable and (
            token.cached_branch is None or token.branch_from_study_prewarm
        ):
            if token.cached_branch is None:
                if (
                    token.request_digest is None
                    or token.configured_provider is None
                    or completion is None
                ):
                    raise MeldApplicationError(
                        "Meld cache publication lacks complete provider evidence."
                    )
                branch = MeldResolutionBranch.create(
                    session=session,
                    request_digest=token.request_digest,
                    configured_provider=token.configured_provider,
                    origin_provider=(
                        origin_provider
                        if isinstance(origin_provider, ProviderIdentity)
                        else None
                    ),
                    completion=completion,
                )
            else:
                branch = token.cached_branch
            self._store.save_meld_resolution_branch(branch)
        self._store.save_meld_session(
            session,
            expected_session_digest=frozen.expected_session_digest,
        )
        return session


def prepare_meld_assessment(
    session: MeldSession,
    *,
    store: MemoryStore,
    expected_session_digest: str | None,
) -> tuple[FrozenMeldAssessment, MemoryStoreMeldAssessmentPort]:
    """Freeze one assessment and return its owning production port."""

    port = MemoryStoreMeldAssessmentPort(store)
    return (
        port.freeze(
            session,
            expected_session_digest=expected_session_digest,
        ),
        port,
    )


@dataclass(frozen=True)
class PreparedMeldTurnExecution:
    """One pending dialogue turn bound to its cache and publication token."""

    pending: PendingMeldTurn
    frozen: FrozenMeldAssessment
    port: MemoryStoreMeldAssessmentPort

    @property
    def provider_required(self) -> bool:
        return self.frozen.cached_completion is None


def prepare_pending_meld_turn(
    pending: PendingMeldTurn,
    *,
    store: MemoryStore,
) -> PreparedMeldTurnExecution:
    """Freeze a locally composed turn through the production cache boundary."""

    if not isinstance(pending, PendingMeldTurn):
        raise TypeError("Meld turn execution requires a PendingMeldTurn.")
    frozen, port = prepare_meld_assessment(
        pending.session,
        store=store,
        expected_session_digest=pending.expected_version,
    )
    return PreparedMeldTurnExecution(pending=pending, frozen=frozen, port=port)


def prepare_meld_turn_execution(
    request: MeldTurnRequest,
    *,
    store: MemoryStore,
) -> PreparedMeldTurnExecution:
    """Compose and freeze one follow-up under the exact saved-session token."""

    return prepare_pending_meld_turn(
        prepare_meld_turn(request),
        store=store,
    )


def execute_meld_assessment(
    frozen: FrozenMeldAssessment,
    *,
    port: MemoryStoreMeldAssessmentPort,
    provider_factory: MeldProviderFactory,
    observer=None,
) -> MeldAssessmentResult:
    """Execute one frozen semantic turn through its owning production port."""

    return run_meld_assessment(
        frozen,
        port=port,
        provider_factory=lambda: connect_meld_provider(provider_factory),
        observer=observer,
    )


def execute_prepared_meld_turn(
    prepared: PreparedMeldTurnExecution,
    *,
    provider_factory: MeldProviderFactory,
    observer=None,
) -> MeldAssessmentResult:
    """Execute the exact frozen cache/provider decision without recomputing it."""

    if not isinstance(prepared, PreparedMeldTurnExecution):
        raise TypeError("Meld turn execution requires prepared input.")
    return execute_meld_assessment(
        prepared.frozen,
        port=prepared.port,
        provider_factory=provider_factory,
        observer=observer,
    )


def execute_meld_turn(
    request: MeldTurnRequest,
    *,
    store: MemoryStore,
    provider_factory: MeldProviderFactory,
    observer=None,
) -> MeldAssessmentResult:
    """Compose, cache-resolve, execute, and CAS-publish one follow-up turn."""

    return execute_prepared_meld_turn(
        prepare_meld_turn_execution(request, store=store),
        provider_factory=provider_factory,
        observer=observer,
    )
