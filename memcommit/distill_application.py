"""Interface-independent orchestration for Distill analysis and Apply."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Protocol

from memcommit.distill import (
    DistillAnalysis,
    DistillError,
    DistillProvider,
    analyze_distill,
)
from memcommit.summarize_application import (
    FrozenSummarySource,
    SummarizeRequest,
    SummarySourcePort,
)


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
) -> DistillResult:
    """Create one proposal and revalidate its complete Source before return."""

    source = source_port.freeze(
        SummarizeRequest(
            context_locator=request.context_locator,
            include_descendants=request.include_descendants,
            follow_embeds=request.follow_embeds,
        )
    )
    with provider_session_factory() as provider:
        analysis = analyze_distill(source.frame, goal=request.goal, provider=provider)
    current = source_port.revalidate(source)
    if current.digest != source.frame.digest:
        raise DistillError(
            "The selected Context changed while Distill was running; no "
            "proposal was published."
        )
    return DistillResult(analysis=analysis, frozen_source=source)


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
