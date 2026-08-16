"""Interface-independent orchestration for Distill analysis and Apply."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Literal, Protocol

from memcommit.distill import (
    DistillAnalysis,
    DistillError,
    DistillProvider,
    analyze_distill,
    validate_distill_analysis,
    validate_distill_input,
    validate_distill_provider_plan,
)
from memcommit.distill_config import (
    DEFAULT_DISTILL_SEMANTIC_CONFIG,
    DistillSemanticConfig,
)
from memcommit.summarize_application import (
    FrozenSummarySource,
    SummarizeRequest,
    SummarySourcePort,
)
from memcommit.summarize import SummaryFrame


@dataclass(frozen=True)
class DistillRequest:
    """One stable Context-to-Rules request independent of argv and TUI state."""

    context_locator: str | None = None
    goal: str | None = None
    include_descendants: bool = False
    follow_embeds: bool = False


@dataclass(frozen=True)
class DistillResult:
    """A reviewed-capable but still non-mutating Distill proposal."""

    analysis: DistillAnalysis
    frozen_source: FrozenSummarySource = field(repr=False, compare=False)
    origin: Literal["LIVE", "PREPARED_EXACT"] = "LIVE"

    def __post_init__(self) -> None:
        if self.origin not in {"LIVE", "PREPARED_EXACT"}:
            raise ValueError("Distill result origin is invalid.")


@dataclass(frozen=True)
class DistillApplyRequest:
    result: DistillResult
    output_name: str


@dataclass(frozen=True)
class DistillApplyReceipt:
    output_name: str
    output_context_uid: str
    checkpoint_uid: str
    result_memory_uids: tuple[str, ...]


class DistillProviderSessionFactory(Protocol):
    def __call__(self) -> AbstractContextManager[DistillProvider]:
        """Open one bounded provider session after the Source is frozen."""


class DistillPreparedLookup(Protocol):
    """Look up only an exact, already-authorized Distill analysis."""

    def __call__(
        self,
        source: SummaryFrame,
        goal: str | None,
        config: DistillSemanticConfig,
    ) -> DistillAnalysis | None:
        """Return an exact result or miss without constructing a provider."""


class DistillOutputPort(Protocol):
    def materialize(
        self,
        request: DistillApplyRequest,
        *,
        source_port: SummarySourcePort,
    ) -> DistillApplyReceipt:
        """Create one require-new Result from the exact reviewed proposal."""


def run_distill(
    request: DistillRequest,
    *,
    source_port: SummarySourcePort,
    provider_session_factory: DistillProviderSessionFactory,
    config: DistillSemanticConfig = DEFAULT_DISTILL_SEMANTIC_CONFIG,
    prepared_lookup: DistillPreparedLookup | None = None,
) -> DistillResult:
    """Create one proposal and revalidate its complete Source before return."""

    source = source_port.freeze(
        SummarizeRequest(
            context_locator=request.context_locator,
            include_descendants=request.include_descendants,
            follow_embeds=request.follow_embeds,
        )
    )
    if (
        source.frame.include_descendants != request.include_descendants
        or source.frame.follow_embeds != request.follow_embeds
    ):
        raise DistillError("The frozen Distill Source does not match its request.")
    goal = validate_distill_input(source.frame, goal=request.goal, config=config)
    analysis = (
        prepared_lookup(source.frame, goal, config)
        if prepared_lookup is not None
        else None
    )
    origin: Literal["LIVE", "PREPARED_EXACT"] = "PREPARED_EXACT"
    if analysis is None:
        origin = "LIVE"
        validate_distill_provider_plan(source.frame, goal=goal, config=config)
        with provider_session_factory() as provider:
            analysis = analyze_distill(
                source.frame,
                goal=goal,
                provider=provider,
                config=config,
            )
    elif (
        analysis.source.digest != source.frame.digest
        or analysis.source != source.frame
        or analysis.goal != goal
    ):
        # A cache adapter is untrusted at the application boundary. Distill is
        # a global reduction, so subset or ancestor projection is not safe.
        raise DistillError(
            "The prepared Distill analysis does not exactly match the frozen request."
        )
    validate_distill_analysis(analysis, config=config)
    current = source_port.revalidate(source)
    if current.digest != source.frame.digest:
        raise DistillError(
            "The selected Context changed while Distill was running; no "
            "proposal was published."
        )
    return DistillResult(
        analysis=analysis,
        frozen_source=source,
        origin=origin,
    )


def apply_distill(
    request: DistillApplyRequest,
    *,
    source_port: SummarySourcePort,
    output_port: DistillOutputPort,
) -> DistillApplyReceipt:
    """Apply only the exact already-reviewed proposal."""

    if not request.result.analysis.rules:
        raise DistillError("Distill produced no supported Rules to materialize.")
    return output_port.materialize(request, source_port=source_port)
