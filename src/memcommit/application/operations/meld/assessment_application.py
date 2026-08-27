"""Terminal-independent semantic assessment lifecycle for saved Melds."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

from memcommit.application.operations.meld.model import (
    MeldAssessment,
    MeldError,
    MeldRepairableAssessmentError,
    MeldSession,
)
from memcommit.application.operations.meld.provider import assess_meld_turn, repair_meld_assessment


MeldAssessmentStage = Literal[
    "CONNECTING_PROVIDER",
    "ANALYZING",
    "REPAIRING",
]
MeldAssessmentOrigin = Literal["CACHE", "PROVIDER"]
MeldAssessmentObserver = Callable[[MeldAssessmentStage], None]
MeldProviderFactory = Callable[[], object]


@dataclass(frozen=True)
class FrozenMeldAssessment:
    """One exact pending turn plus an opaque Store/cache publication binding."""

    session: MeldSession
    expected_session_digest: str | None
    cached_completion: str | None
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class MeldAssessmentResult:
    """One complete assessed session and how its semantic result was obtained."""

    session: MeldSession
    assessment: MeldAssessment
    origin: MeldAssessmentOrigin


class MeldAssessmentPort(Protocol):
    """Freeze cache state and atomically publish one complete assessed turn."""

    def freeze(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str | None,
    ) -> FrozenMeldAssessment:
        """Return one exact pending turn and any valid complete cached response."""

    def commit(
        self,
        frozen: FrozenMeldAssessment,
        *,
        session: MeldSession,
        assessment: MeldAssessment,
        completion: str | None,
        origin_provider: object | None,
    ) -> MeldSession:
        """Revalidate live inputs and publish cache/session state or no result."""


class _CapturingProvider:
    def __init__(self, provider: object):
        self.provider = provider
        self.last_completion: str | None = None

    def complete(self, prompt, *, operation, output_schema=None):
        completion = self.provider.complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )
        self.last_completion = completion
        return completion


class _SavedCompletionProvider:
    def __init__(self, completion: str):
        self.completion = completion
        self.called = False

    def complete(self, prompt, *, operation, output_schema=None):
        if self.called or operation != "meld_contexts":
            raise MeldError("Saved Meld branch replay is invalid.")
        self.called = True
        return self.completion


def _observe(
    observer: MeldAssessmentObserver | None,
    stage: MeldAssessmentStage,
) -> None:
    if observer is not None:
        observer(stage)


def _incorporate(
    session: MeldSession,
    provider: object,
    *,
    repair: bool,
    observer: MeldAssessmentObserver | None,
) -> tuple[MeldSession, MeldAssessment]:
    assessment = assess_meld_turn(session, provider)
    try:
        candidate = MeldSession.from_dict(session.to_dict())
        current = candidate.current_turn
        assert current is not None
        candidate.record_assessment(current.uid, assessment)
    except MeldRepairableAssessmentError as validation_error:
        if not repair:
            raise
        _observe(observer, "REPAIRING")
        try:
            assessment = repair_meld_assessment(
                session,
                assessment,
                str(validation_error),
                provider,
            )
            candidate = MeldSession.from_dict(session.to_dict())
            current = candidate.current_turn
            assert current is not None
            candidate.record_assessment(current.uid, assessment)
        except MeldError as repair_error:
            raise MeldError(
                "Meld validation repair failed after the initial response "
                f"was rejected ({validation_error}): {repair_error}"
            ) from repair_error
    return candidate, assessment


def run_meld_assessment(
    frozen: FrozenMeldAssessment,
    *,
    port: MeldAssessmentPort,
    provider_factory: MeldProviderFactory,
    observer: MeldAssessmentObserver | None = None,
) -> MeldAssessmentResult:
    """Reuse one complete branch or perform exactly one bounded provider turn."""

    if not isinstance(frozen, FrozenMeldAssessment):
        raise TypeError("Meld assessment requires frozen input.")
    if frozen.cached_completion is not None:
        candidate, assessment = _incorporate(
            frozen.session,
            _SavedCompletionProvider(frozen.cached_completion),
            repair=False,
            observer=None,
        )
        completion = None
        origin_provider = None
        origin: MeldAssessmentOrigin = "CACHE"
    else:
        _observe(observer, "CONNECTING_PROVIDER")
        provider = _CapturingProvider(provider_factory())
        _observe(observer, "ANALYZING")
        candidate, assessment = _incorporate(
            frozen.session,
            provider,
            repair=True,
            observer=observer,
        )
        completion = provider.last_completion
        if completion is None:
            raise MeldError("Meld provider returned no captured completion.")
        origin_provider = getattr(provider.provider, "identity", None)
        origin = "PROVIDER"
    committed = port.commit(
        frozen,
        session=candidate,
        assessment=assessment,
        completion=completion,
        origin_provider=origin_provider,
    )
    if committed is not candidate:
        raise MeldError("Meld assessment persistence replaced the reviewed session.")
    return MeldAssessmentResult(
        session=committed,
        assessment=assessment,
        origin=origin,
    )


__all__ = [
    "FrozenMeldAssessment",
    "MeldAssessmentObserver",
    "MeldAssessmentOrigin",
    "MeldAssessmentPort",
    "MeldAssessmentResult",
    "MeldAssessmentStage",
    "MeldProviderFactory",
    "run_meld_assessment",
]
