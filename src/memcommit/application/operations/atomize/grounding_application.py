"""Operation-owned contract for conversational Atomize Grounding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, ContextManager, Protocol

from memcommit.application.operations.atomize.domain import AtomizeAnalysisSession
from memcommit.application.operations.atomize.grounding import AtomizeGroundingSession
from memcommit.application.operations.atomize.grounding_provider import AtomizeGroundingProvider
from memcommit.application.operations.atomize.workbench import AtomizeWorkbenchSession
from memcommit.context import Context


AtomizeGroundingProviderFactory = Callable[[], AtomizeGroundingProvider]
AtomizeGroundingProviderProgress = Callable[
    [str, AtomizeGroundingProviderFactory],
    ContextManager[AtomizeGroundingProviderFactory],
]


class AtomizeGroundingApplicationError(RuntimeError):
    """A dialogue or application request crossed a safe Grounding boundary."""


@dataclass(frozen=True)
class GroundingStartRequest:
    """Start one dialogue against an exact analysis/workbench revision."""

    context: Context
    analysis: AtomizeAnalysisSession
    workbench: AtomizeWorkbenchSession
    selector: str
    comment: str


@dataclass(frozen=True)
class GroundingReplyRequest:
    """Append one explicit revision to the current dialogue."""

    context: Context
    analysis: AtomizeAnalysisSession
    workbench: AtomizeWorkbenchSession
    reply: str
    revision: str = "EXTEND"


@dataclass(frozen=True)
class GroundingKeepRequest:
    """Close one dialogue as durable review evidence without mutation."""

    context_uid: str


@dataclass(frozen=True)
class GroundingAcceptRequest:
    """Apply the exact accepted proposal bound to one saved revision."""

    context: Context
    analysis: AtomizeAnalysisSession
    workbench: AtomizeWorkbenchSession


@dataclass(frozen=True)
class GroundingApplyResult:
    """One successful or recovered one-checkpoint application."""

    checkpoint_uid: str
    change_count: int
    recovered: bool = False


class AtomizeGroundingPort(Protocol):
    """Persist dialogue turns and materialize an approved Grounding proposal."""

    def start(
        self,
        request: GroundingStartRequest,
        *,
        provider_factory: AtomizeGroundingProviderFactory,
    ) -> AtomizeGroundingSession: ...

    def reply(
        self,
        request: GroundingReplyRequest,
        *,
        provider_factory: AtomizeGroundingProviderFactory,
    ) -> AtomizeGroundingSession: ...

    def keep(self, request: GroundingKeepRequest) -> AtomizeGroundingSession: ...

    def accept(self, request: GroundingAcceptRequest) -> GroundingApplyResult: ...


def _validate_bound_session(
    session: AtomizeGroundingSession,
    *,
    context_uid: str,
    context_name: str | None = None,
) -> AtomizeGroundingSession:
    if session.bindings.context_uid != context_uid or (
        context_name is not None
        and session.bindings.context_name != context_name
    ):
        raise AtomizeGroundingApplicationError(
            "Atomize Grounding returned a dialogue for a different Context."
        )
    return session


def run_atomize_grounding_start(
    request: GroundingStartRequest,
    *,
    port: AtomizeGroundingPort,
    provider_factory: AtomizeGroundingProviderFactory,
) -> AtomizeGroundingSession:
    """Start and assess one dialogue without depending on a terminal."""

    if not isinstance(request, GroundingStartRequest):
        raise TypeError("Atomize Grounding start requires a typed request.")
    return _validate_bound_session(
        port.start(request, provider_factory=provider_factory),
        context_uid=request.context.uid,
        context_name=request.context.name,
    )


def run_atomize_grounding_reply(
    request: GroundingReplyRequest,
    *,
    port: AtomizeGroundingPort,
    provider_factory: AtomizeGroundingProviderFactory,
) -> AtomizeGroundingSession:
    """Append and assess one turn without depending on a terminal."""

    if not isinstance(request, GroundingReplyRequest):
        raise TypeError("Atomize Grounding reply requires a typed request.")
    return _validate_bound_session(
        port.reply(request, provider_factory=provider_factory),
        context_uid=request.context.uid,
        context_name=request.context.name,
    )


def run_atomize_grounding_keep(
    request: GroundingKeepRequest,
    *,
    port: AtomizeGroundingPort,
) -> AtomizeGroundingSession:
    """Close one dialogue without changing its bound Context."""

    if not isinstance(request, GroundingKeepRequest):
        raise TypeError("Atomize Grounding keep requires a typed request.")
    session = _validate_bound_session(
        port.keep(request),
        context_uid=request.context_uid,
    )
    if session.state != "KEPT_REVIEW_ONLY":
        raise AtomizeGroundingApplicationError(
            "Atomize Grounding keep did not close the dialogue as review-only."
        )
    return session


def run_atomize_grounding_accept(
    request: GroundingAcceptRequest,
    *,
    port: AtomizeGroundingPort,
) -> GroundingApplyResult:
    """Apply or recover one exact complete Grounding proposal."""

    if not isinstance(request, GroundingAcceptRequest):
        raise TypeError("Atomize Grounding accept requires a typed request.")
    result = port.accept(request)
    if not result.checkpoint_uid or result.change_count < 1:
        raise AtomizeGroundingApplicationError(
            "Atomize Grounding returned an incomplete application receipt."
        )
    return result


__all__ = [
    "AtomizeGroundingApplicationError",
    "AtomizeGroundingPort",
    "AtomizeGroundingProviderFactory",
    "AtomizeGroundingProviderProgress",
    "GroundingAcceptRequest",
    "GroundingApplyResult",
    "GroundingKeepRequest",
    "GroundingReplyRequest",
    "GroundingStartRequest",
    "run_atomize_grounding_accept",
    "run_atomize_grounding_keep",
    "run_atomize_grounding_reply",
    "run_atomize_grounding_start",
]
