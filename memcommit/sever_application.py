"""Terminal-independent application boundary for Sever analysis and Apply."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.sever import SeverContextBinding, SeverSession
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
    """The exact reviewed session requested for require-new materialization."""

    session: SeverSession


@dataclass(frozen=True)
class SeverApplyResult:
    """The applied receipt-bearing session and whether this call created it."""

    session: SeverSession
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
    """Materialize one reviewed session through a require-new output boundary."""

    def materialize(self, session: SeverSession) -> SeverSession:
        """Return the same review advanced to its durable APPLIED state."""


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
    return SeverApplyResult(session=applied, created=True)
