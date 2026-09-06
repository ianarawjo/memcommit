"""Production Sever entry points and session/provider adapter wiring."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.sever.application import (
    FrozenSeverInputs,
    SeverPreparedAnalysis,
    SeverAnalysisRequest,
    SeverAnalysisResult,
    SeverApplicationError,
    SeverApplyRequest,
    SeverApplyResult,
    SeverDecisionRequest,
    SeverDestinationRequest,
    SeverPersistedApplyRequest,
    SeverPersistedApplyResult,
    SeverProgressObserver,
    SeverProviderFactory,
    SeverSessionSnapshot,
    SeverStoredAnalysisResult,
    run_sever_analysis,
    run_sever_apply,
    run_sever_session_apply,
    run_sever_session_decision,
    run_sever_session_destination_change,
    run_sever_session_open,
    run_sever_session_start,
)
from memcommit.application.operations.sever.apply.execution import (
    MemoryStoreSeverOutputPort as MemoryStoreSeverOutputPort,
)
from memcommit.application.operations.sever.inputs import (
    MemoryStoreSeverInputPort as MemoryStoreSeverInputPort,
)
from memcommit.application.operations.sever.inputs import (
    capture_sever_binding as capture_sever_binding,
)
from memcommit.application.operations.sever.model import (
    SeverSession,
    sever_record_digest,
)
from memcommit.application.operations.sever.provider import SeverProviderError
from memcommit.application.operations.sever.session_store import SeverSessionStore
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.command_ledger.attempts import annotate_sever_attempt
from memcommit.persistence.store import (
    MemoryStore,
)
from memcommit.providers.subscription import (
    QueryProviderError,
    QueryProviderTimeoutError,
)

from memcommit.study_scenarios.legacy.prewarm.sever import (
    find_installed_projectable_sever_prewarm,
)

SeverProgressCallback = SeverProgressObserver


@dataclass
class MemoryStoreSeverSessionRepository:
    """Private Store-backed session persistence with opaque digest CAS tokens."""

    store: MemoryStore

    @property
    def sessions(self) -> SeverSessionStore:
        return SeverSessionStore(self.store)

    @staticmethod
    def _snapshot(session: SeverSession) -> SeverSessionSnapshot:
        return SeverSessionSnapshot(
            session=session,
            version_token=sever_record_digest(session),
        )

    def create(self, session: SeverSession) -> SeverSessionSnapshot:
        self.sessions.save(session, expected_digest=None)
        return self._snapshot(session)

    def load(self, uid: str) -> SeverSessionSnapshot:
        return self._snapshot(self.sessions.load(uid))

    def replace(
        self,
        session: SeverSession,
        *,
        expected_version: str,
    ) -> SeverSessionSnapshot:
        self.sessions.save(session, expected_digest=expected_version)
        return self._snapshot(session)


@dataclass
class MemoryStoreSeverDestinationPort:
    """Validate one local self- or other-save destination against the live Store."""

    store: MemoryStore
    source_name: str
    self_save_allowed: bool

    def validate(self, output_name: str, *, current_output_name: str) -> None:
        validate_portable_context_name(output_name)
        if output_name == self.source_name:
            if not self.self_save_allowed:
                raise SeverApplicationError(
                    "In-place Sever requires an ordinary local Source root."
                )
            return
        if output_name != current_output_name and self.store.context_exists(
            output_name
        ):
            raise SeverApplicationError(
                f"Output Context '{output_name}' already exists."
            )


def _provider_with_attempt_evidence(factory: SeverProviderFactory) -> object:
    provider = factory()
    identity = getattr(provider, "identity", None)
    provider_name = getattr(identity, "provider", None)
    provider_timeout = getattr(provider, "timeout", None)
    details: dict[str, object] = {}
    if isinstance(provider_name, str) and provider_name:
        details["provider"] = provider_name
    if (
        isinstance(provider_timeout, (int, float))
        and not isinstance(provider_timeout, bool)
        and provider_timeout > 0
    ):
        details["provider_timeout_seconds"] = provider_timeout
    if details:
        annotate_sever_attempt(**details)
    return provider


def execute_sever_analysis(
    request: SeverAnalysisRequest,
    *,
    store: MemoryStore,
    provider_factory: SeverProviderFactory,
    progress_callback: SeverProgressCallback | None = None,
) -> SeverAnalysisResult:
    """Execute Sever analysis with no CLI, TUI, or terminal output."""

    input_port = MemoryStoreSeverInputPort.capture(store)
    try:
        return run_sever_analysis(
            request,
            input_port=input_port,
            provider_factory=lambda: _provider_with_attempt_evidence(provider_factory),
            prepared_lookup=lambda inputs, output_name: _prepared_analysis(
                store,
                inputs,
                output_name,
            ),
            progress_observer=progress_callback,
        )
    except QueryProviderError as error:
        annotate_sever_attempt(
            failure_kind=(
                "TIMEOUT"
                if isinstance(error, QueryProviderTimeoutError)
                else "PROVIDER"
            )
        )
        frozen = input_port.last_frozen
        frame = (
            f" Prepared input: {len(frozen.source.memories)} Source Memories x "
            f"{len(frozen.criteria.memories)} Criteria Memories."
            if frozen is not None
            else ""
        )
        raise SeverApplicationError(f"{error}{frame}") from error
    except SeverProviderError:
        annotate_sever_attempt(failure_kind="VALIDATION")
        raise


def _prepared_analysis(
    store: MemoryStore,
    inputs: FrozenSeverInputs,
    output_name: str,
) -> SeverPreparedAnalysis | None:
    match = find_installed_projectable_sever_prewarm(
        store=store,
        source=inputs.source,
        criteria=inputs.criteria,
        output_name=output_name,
    )
    if match is None:
        return None
    if match.origin == "EXACT_PREWARM":
        return SeverPreparedAnalysis(
            session=match.session,
            origin="EXACT_PREWARM",
        )
    if match.origin == "EQUIVALENT_SCOPE_PREWARM":
        return SeverPreparedAnalysis(
            session=match.session,
            origin="EQUIVALENT_SCOPE_PREWARM",
        )
    if match.origin == "PROJECTED_PREWARM":
        return SeverPreparedAnalysis(
            session=match.session,
            origin="PROJECTED_PREWARM",
        )
    raise SeverApplicationError(
        "The prepared Sever analysis has an unsupported origin."
    )


def execute_sever_apply(
    request: SeverApplyRequest,
    *,
    store: MemoryStore,
) -> SeverApplyResult:
    """Apply one exact review through the production save-location port."""

    return run_sever_apply(
        request,
        output_port=MemoryStoreSeverOutputPort(store),
    )


def execute_sever_session_start(
    analysis: SeverAnalysisResult,
    *,
    store: MemoryStore,
) -> SeverStoredAnalysisResult:
    """Persist one newly analyzed review through the private session adapter."""

    return run_sever_session_start(
        analysis,
        repository=MemoryStoreSeverSessionRepository(store),
    )


def execute_sever_session_open(
    uid: str,
    *,
    store: MemoryStore,
) -> SeverSessionSnapshot:
    """Load one exact saved session without terminal or interface behavior."""

    return run_sever_session_open(
        uid,
        repository=MemoryStoreSeverSessionRepository(store),
    )


def execute_sever_session_decision(
    request: SeverDecisionRequest,
    *,
    store: MemoryStore,
) -> SeverSessionSnapshot:
    """Persist one reviewed candidate decision under session CAS."""

    return run_sever_session_decision(
        request,
        repository=MemoryStoreSeverSessionRepository(store),
    )


def execute_sever_session_destination_change(
    request: SeverDestinationRequest,
    *,
    store: MemoryStore,
) -> SeverSessionSnapshot:
    """Validate and persist one self- or other-save destination revision."""

    session = request.snapshot.session
    return run_sever_session_destination_change(
        request,
        repository=MemoryStoreSeverSessionRepository(store),
        destination_port=MemoryStoreSeverDestinationPort(
            store,
            source_name=session.source.root_name,
            self_save_allowed=(session.source.granted is None),
        ),
    )


def execute_sever_session_apply(
    request: SeverPersistedApplyRequest,
    *,
    store: MemoryStore,
) -> SeverPersistedApplyResult:
    """Materialize and persist one saved review through the lifecycle boundary."""

    return run_sever_session_apply(
        request,
        repository=MemoryStoreSeverSessionRepository(store),
        output_port=MemoryStoreSeverOutputPort(store),
    )
