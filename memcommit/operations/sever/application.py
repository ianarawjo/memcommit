"""Operation-owned application boundary for Sever analysis and Apply."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.application_flow import run_application_flow
from memcommit.sever import SeverContextBinding, SeverSelection, SeverSession
from memcommit.sever_provider import analyze_sever


class SeverApplicationError(RuntimeError):
    """A Sever use case could not safely reach its requested outcome."""


@dataclass(frozen=True)
class SeverAnalysisRequest:
    """One Source × Criteria analysis request independent of argv or TUI state."""

    source_locator: str
    criteria_locator: str
    output_name: str
    source_include_descendants: bool = True
    criteria_include_descendants: bool = True


@dataclass(frozen=True)
class FrozenSeverInputs:
    """Authorized, immutable provider inputs captured for one analysis turn."""

    source: SeverContextBinding
    criteria: SeverContextBinding


SeverPreparedOrigin = Literal[
    "EXACT_PREWARM",
    "EQUIVALENT_SCOPE_PREWARM",
    "PROJECTED_PREWARM",
]
SeverAnalysisOrigin = Literal[
    "PROVIDER",
    "EXACT_PREWARM",
    "EQUIVALENT_SCOPE_PREWARM",
    "PROJECTED_PREWARM",
]
SeverAnalysisStage = Literal[
    "INPUTS_FROZEN",
    "PREPARED_REUSED",
    "CONNECTING_PROVIDER",
    "ANALYZING",
]


@dataclass(frozen=True)
class SeverAnalysisProgress:
    """Typed lifecycle evidence that a host may project into its own UI."""

    stage: SeverAnalysisStage
    source_count: int
    criteria_count: int


@dataclass(frozen=True)
class SeverAnalysisResult:
    """A complete retained review and how its semantic analysis was obtained."""

    session: SeverSession
    origin: SeverAnalysisOrigin


@dataclass(frozen=True)
class SeverPreparedAnalysis:
    """One adapter-authorized prepared review and its projection relation."""

    session: SeverSession
    origin: SeverPreparedOrigin


@dataclass(frozen=True)
class SeverApplyRequest:
    """The exact reviewed session requested for self- or other-save Apply."""

    session: SeverSession


@dataclass(frozen=True)
class SeverApplyResult:
    """The applied receipt-bearing session and whether this call created it."""

    session: SeverSession
    created: bool


@dataclass(frozen=True)
class SeverSessionSnapshot:
    """One validated durable session plus its opaque optimistic-CAS token."""

    session: SeverSession
    version_token: str

    def __post_init__(self) -> None:
        if not self.version_token:
            raise SeverApplicationError("A saved Sever session requires a version token.")


@dataclass(frozen=True)
class SeverStoredAnalysisResult:
    """A newly saved review and the origin of its semantic analysis."""

    snapshot: SeverSessionSnapshot
    origin: SeverAnalysisOrigin


@dataclass(frozen=True)
class SeverDecisionRequest:
    """One exact review decision against a previously opened session version."""

    snapshot: SeverSessionSnapshot
    candidate_uid: str
    selection: SeverSelection
    custom_content: str = ""


@dataclass(frozen=True)
class SeverDestinationRequest:
    """Rebind an unapplied review to one validated save location."""

    snapshot: SeverSessionSnapshot
    output_name: str


@dataclass(frozen=True)
class SeverPersistedApplyRequest:
    """Apply and persist one exact saved review under its version token."""

    snapshot: SeverSessionSnapshot


@dataclass(frozen=True)
class SeverPersistedApplyResult:
    """The durable APPLIED snapshot and whether this call created the output."""

    snapshot: SeverSessionSnapshot
    created: bool


class SeverInputPort(Protocol):
    """Resolve authority and freeze the exact Source and Criteria frames."""

    def freeze(self, request: SeverAnalysisRequest) -> FrozenSeverInputs:
        """Return complete inputs only after all pre-disclosure checks pass."""


class SeverPreparedLookup(Protocol):
    """Look up one exact prepared review for already-authorized inputs."""

    def __call__(
        self,
        inputs: FrozenSeverInputs,
        output_name: str,
    ) -> SeverPreparedAnalysis | None:
        """Return a fresh review or ``None`` without broadening either frame."""


class SeverProviderFactory(Protocol):
    """Construct the configured semantic provider lazily after cache lookup."""

    def __call__(self) -> object:
        """Return one provider for the complete Source × Criteria turn."""


SeverProgressObserver = Callable[[SeverAnalysisProgress], None]


class SeverOutputPort(Protocol):
    """Materialize one reviewed session through its exact save-location boundary."""

    def recover_materialization(self, session: SeverSession) -> SeverSession | None:
        """Recover an exact pre-existing Result whose receipt was not saved."""

    def materialize(self, session: SeverSession) -> SeverSession:
        """Return the same review advanced to its durable APPLIED state."""

    def rollback_materialization(self, applied: SeverSession) -> None:
        """Remove only the exact output created for an uncommitted receipt."""


class SeverSessionRepository(Protocol):
    """Persist private review sessions without exposing filesystem mechanics."""

    def create(self, session: SeverSession) -> SeverSessionSnapshot:
        """Create one previously absent session and return its CAS snapshot."""

    def load(self, uid: str) -> SeverSessionSnapshot:
        """Load one exact durable session and its current CAS token."""

    def replace(
        self,
        session: SeverSession,
        *,
        expected_version: str,
    ) -> SeverSessionSnapshot:
        """Replace one session only if its opaque version token is unchanged."""


class SeverDestinationPort(Protocol):
    """Validate one local self- or other-save location against runtime state."""

    def validate(self, output_name: str, *, current_output_name: str) -> None:
        """Fail unless the proposed destination remains safe for this review."""


def _observe(
    observer: SeverProgressObserver | None,
    stage: SeverAnalysisStage,
    inputs: FrozenSeverInputs,
) -> None:
    if observer is not None:
        observer(
            SeverAnalysisProgress(
                stage=stage,
                source_count=len(inputs.source.memories),
                criteria_count=len(inputs.criteria.memories),
            )
        )


def _validated_review(
    session: SeverSession,
    *,
    inputs: FrozenSeverInputs,
    output_name: str,
) -> SeverSession:
    # Exact prepared artifacts and live provider results cross the same
    # boundary. Validate both so a cache adapter cannot publish a wider or
    # differently targeted review than the authorized request.
    if (
        session.state != "REVIEWING"
        or session.application is not None
        or session.source != inputs.source
        or session.criteria != inputs.criteria
        or session.output_name != output_name
    ):
        raise SeverApplicationError(
            "Sever analysis returned a review outside the frozen request."
        )
    return session


def run_sever_analysis(
    request: SeverAnalysisRequest,
    *,
    input_port: SeverInputPort,
    provider_factory: SeverProviderFactory,
    prepared_lookup: SeverPreparedLookup | None = None,
    progress_observer: SeverProgressObserver | None = None,
) -> SeverAnalysisResult:
    """Create one complete review without CLI, TUI, or durable output effects."""

    inputs = input_port.freeze(request)
    _observe(progress_observer, "INPUTS_FROZEN", inputs)

    prepared = (
        prepared_lookup(inputs, request.output_name)
        if prepared_lookup is not None
        else None
    )
    if prepared is not None:
        validated = _validated_review(
            prepared.session,
            inputs=inputs,
            output_name=request.output_name,
        )
        _observe(progress_observer, "PREPARED_REUSED", inputs)
        return SeverAnalysisResult(
            session=validated,
            origin=prepared.origin,
        )

    _observe(progress_observer, "CONNECTING_PROVIDER", inputs)
    provider = provider_factory()
    _observe(progress_observer, "ANALYZING", inputs)
    session = analyze_sever(
        inputs.source,
        inputs.criteria,
        request.output_name,
        provider,
    )
    return SeverAnalysisResult(
        session=_validated_review(
            session,
            inputs=inputs,
            output_name=request.output_name,
        ),
        origin="PROVIDER",
    )


def run_sever_apply(
    request: SeverApplyRequest,
    *,
    output_port: SeverOutputPort,
) -> SeverApplyResult:
    """Materialize one reviewed result while preserving its frozen inputs."""

    session = request.session
    if session.state == "APPLIED":
        return SeverApplyResult(session=session, created=False)

    applied = output_port.materialize(session)
    _validate_applied_session(session, applied)
    return SeverApplyResult(session=applied, created=True)


def _validate_applied_session(
    session: SeverSession,
    applied: SeverSession,
) -> None:
    """Reject a materialization receipt outside its exact reviewed session."""

    if (
        applied.state != "APPLIED"
        or applied.application is None
        or applied.revision != session.revision + 1
        or applied.source != session.source
        or applied.criteria != session.criteria
        or applied.output_name != session.output_name
        or applied.overview != session.overview
        or applied.candidates != session.candidates
        or applied.applied_summary != session.applied_summary
    ):
        raise SeverApplicationError(
            "Sever Apply returned a receipt outside the reviewed session."
        )


def _validated_snapshot(
    snapshot: SeverSessionSnapshot,
    *,
    expected_session: SeverSession,
) -> SeverSessionSnapshot:
    if snapshot.session != expected_session:
        raise SeverApplicationError(
            "Sever session persistence returned a different session."
        )
    return snapshot


@dataclass(frozen=True)
class SeverSessionApplicationFlowPort:
    """Adapt a decision-complete saved Sever session to shared phase order.

    Sever decisions and destination changes are already durable session
    revisions before final acceptance. Consequently this adapter's decision
    phase is intentionally an identity handoff: the command owns the visible
    decision loop, while this port preserves the exact accepted CAS snapshot for
    the selected self- or other-save materialization transaction.
    """

    repository: SeverSessionRepository
    output_port: SeverOutputPort

    def decide(
        self,
        prepared: SeverSessionSnapshot,
    ) -> SeverSessionSnapshot:
        """Hand off the exact snapshot accepted by the operation host."""

        return prepared

    def apply(
        self,
        decided: SeverSessionSnapshot,
    ) -> SeverPersistedApplyResult:
        """Save the Result and commit its session receipt as one outcome."""

        current = self.repository.load(decided.session.uid)
        if current != decided:
            raise SeverApplicationError(
                "The Sever session changed before Apply. Reopen its decisions."
            )
        if current.session.state == "APPLIED":
            return SeverPersistedApplyResult(
                snapshot=current,
                created=False,
            )
        recovered = self.output_port.recover_materialization(current.session)
        if recovered is None:
            applied = run_sever_apply(
                SeverApplyRequest(session=current.session),
                output_port=self.output_port,
            )
        else:
            _validate_applied_session(current.session, recovered)
            applied = SeverApplyResult(session=recovered, created=False)
        try:
            snapshot = _validated_snapshot(
                self.repository.replace(
                    applied.session,
                    expected_version=current.version_token,
                ),
                expected_session=applied.session,
            )
        except Exception as error:
            # A replace implementation may report an error after its durable
            # rename. Re-read before compensating so a committed receipt never
            # loses the Result it names.
            try:
                observed = self.repository.load(current.session.uid)
            except Exception as observation_error:
                raise SeverApplicationError(
                    "Sever Result creation succeeded, but receipt persistence "
                    "failed and its durable state could not be verified."
                ) from observation_error
            if observed.session == applied.session:
                return SeverPersistedApplyResult(
                    snapshot=observed,
                    created=applied.created,
                )
            if observed != current:
                raise SeverApplicationError(
                    "Sever Result creation succeeded, but the session changed "
                    "before its receipt could be committed."
                ) from error
            if applied.created:
                try:
                    self.output_port.rollback_materialization(applied.session)
                except Exception as rollback_error:
                    raise SeverApplicationError(
                        "Sever receipt persistence failed and the exact new Result "
                        "could not be rolled back."
                    ) from rollback_error
            raise
        return SeverPersistedApplyResult(
            snapshot=snapshot,
            created=applied.created,
        )


def run_sever_session_start(
    analysis: SeverAnalysisResult,
    *,
    repository: SeverSessionRepository,
) -> SeverStoredAnalysisResult:
    """Persist one complete analysis as a new private review session."""

    session = analysis.session
    if session.state != "REVIEWING" or session.application is not None:
        raise SeverApplicationError("Only a fresh Sever review can start a session.")
    snapshot = _validated_snapshot(
        repository.create(session),
        expected_session=session,
    )
    return SeverStoredAnalysisResult(snapshot=snapshot, origin=analysis.origin)


def run_sever_session_open(
    uid: str,
    *,
    repository: SeverSessionRepository,
) -> SeverSessionSnapshot:
    """Open one exact saved session through the application-owned repository."""

    snapshot = repository.load(uid)
    if snapshot.session.uid != uid:
        raise SeverApplicationError(
            "Sever session persistence returned a different session identity."
        )
    return snapshot


def run_sever_session_decision(
    request: SeverDecisionRequest,
    *,
    repository: SeverSessionRepository,
) -> SeverSessionSnapshot:
    """Persist one exact candidate decision under optimistic session CAS."""

    custom = request.custom_content
    if request.selection == "CUSTOM":
        if not custom.strip():
            raise SeverApplicationError(
                "A custom Sever decision requires nonempty result content."
            )
    elif custom:
        raise SeverApplicationError(
            "Custom Sever content is valid only for a CUSTOM decision."
        )
    changed = request.snapshot.session.select(
        request.candidate_uid,
        request.selection,
        custom,
    )
    return _validated_snapshot(
        repository.replace(
            changed,
            expected_version=request.snapshot.version_token,
        ),
        expected_session=changed,
    )


def run_sever_session_destination_change(
    request: SeverDestinationRequest,
    *,
    repository: SeverSessionRepository,
    destination_port: SeverDestinationPort,
) -> SeverSessionSnapshot:
    """Validate and persist one review destination revision."""

    session = request.snapshot.session
    destination_port.validate(
        request.output_name,
        current_output_name=session.output_name,
    )
    changed = session.with_output_name(request.output_name)
    if changed is session:
        return request.snapshot
    return _validated_snapshot(
        repository.replace(
            changed,
            expected_version=request.snapshot.version_token,
        ),
        expected_session=changed,
    )


def run_sever_session_apply(
    request: SeverPersistedApplyRequest,
    *,
    repository: SeverSessionRepository,
    output_port: SeverOutputPort,
) -> SeverPersistedApplyResult:
    """Materialize and CAS-save one reviewed session through one use case."""

    flow = run_application_flow(
        request.snapshot,
        port=SeverSessionApplicationFlowPort(
            repository=repository,
            output_port=output_port,
        ),
    )
    if flow.applied is None:  # The identity review cannot cancel this use case.
        raise SeverApplicationError("Accepted Sever Apply was cancelled internally.")
    return flow.applied
