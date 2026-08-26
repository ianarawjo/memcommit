"""Operation-owned orchestration for one Summarize request."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Protocol

from memcommit.operations.summarize.model import (
    SummarizeError,
    SummarizeProvider,
    SummaryFrame,
    summarize_frame,
)
from memcommit.semantic.understanding import UnderstandingSummary


@dataclass(frozen=True)
class SummarizeRequest:
    """One stable application request, independent of argv and terminal state."""

    context_locator: str | None = None
    include_descendants: bool = False
    follow_embeds: bool = False


@dataclass(frozen=True)
class FrozenSummarySource:
    """Authorized source frame plus an opaque revalidation binding."""

    frame: SummaryFrame
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class SummarizeResult:
    """Typed read-only outcome shared by future public interfaces."""

    context_name: str
    include_descendants: bool
    follow_embeds: bool
    source_digest: str
    source_count: int
    understanding: UnderstandingSummary


class SummarySourcePort(Protocol):
    """Freeze authorized evidence and later rebuild that exact source."""

    def freeze(self, request: SummarizeRequest) -> FrozenSummarySource:
        """Return a frame only after locator and READ authority validation."""

    def revalidate(self, source: FrozenSummarySource) -> SummaryFrame:
        """Rebuild the frozen frame after revalidating its authority binding."""


class SummaryProviderSessionFactory(Protocol):
    """Open one bounded provider session without exposing transport details."""

    def __call__(self) -> AbstractContextManager[SummarizeProvider]:
        """Yield the provider used for exactly one nonempty summary frame."""


class SummaryPreparedLookup(Protocol):
    """Resolve one exact prepared result without broadening its source frame."""

    def __call__(self, frame: SummaryFrame) -> UnderstandingSummary | None:
        """Return a prepared understanding only for this exact frozen frame."""


class _UnavailableProvider:
    """Fail if an empty frame accidentally reaches semantic infrastructure."""

    def complete(self, *args, **kwargs) -> str:
        raise AssertionError("An empty summary frame must not call a provider.")


def run_summarize(
    request: SummarizeRequest,
    *,
    source_port: SummarySourcePort,
    provider_session_factory: SummaryProviderSessionFactory,
    prepared_lookup: SummaryPreparedLookup | None = None,
) -> SummarizeResult:
    """Run the read-only Summarize use case without CLI or TUI dependencies."""

    source = source_port.freeze(request)
    frame = source.frame
    if (
        frame.include_descendants != request.include_descendants
        or frame.follow_embeds != request.follow_embeds
    ):
        raise SummarizeError(
            "The frozen summary source does not match the requested reach."
        )

    if frame.sources:
        understanding = prepared_lookup(frame) if prepared_lookup is not None else None
        if understanding is None:
            with provider_session_factory() as provider:
                understanding = summarize_frame(frame, provider)
        elif any(
            uid not in {source.memory_uid for source in frame.sources}
            for uid in understanding.source_uids
        ):
            raise SummarizeError(
                "The prepared summary cites evidence outside the frozen frame."
            )
    else:
        understanding = summarize_frame(frame, _UnavailableProvider())

    current_frame = source_port.revalidate(source)
    if current_frame.digest != frame.digest:
        raise SummarizeError(
            "The selected Context changed while summarization was running; "
            "no summary was published."
        )

    return SummarizeResult(
        context_name=frame.context_name,
        include_descendants=frame.include_descendants,
        follow_embeds=frame.follow_embeds,
        source_digest=frame.digest,
        source_count=len(frame.sources),
        understanding=understanding,
    )
