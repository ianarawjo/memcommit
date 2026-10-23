"""Terminal-independent application contract for Context status inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.source_projection.model import SourceDisplayFacts


_MEMORY_PREVIEW_LIMIT = 5
_RECENT_CHECKPOINT_LIMIT = 5


class StatusError(RuntimeError):
    """Base failure for one read-only Status request."""


class NoCurrentStatusContextError(StatusError):
    """Raised when Status has no current Context to inspect."""


@dataclass(frozen=True, slots=True)
class StatusRequest:
    """One Context status scope with optional lexical descendants."""

    include_descendants: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.include_descendants, bool):
            raise TypeError("Status descendant reach must be a boolean.")


@dataclass(frozen=True, slots=True)
class StatusMemory:
    """One ordinary direct Memory eligible for the bounded preview."""

    uid: str
    content: str


@dataclass(frozen=True, slots=True)
class StatusCheckpoint:
    """One content-free checkpoint summary, already ordered newest first."""

    uid: str
    timestamp: str
    command: str
    description: str
    automatic: bool


@dataclass(frozen=True, slots=True)
class FrozenStatusContext:
    """Complete direct facts frozen by the Status infrastructure port."""

    uid: str
    name: str
    source: SourceDisplayFacts
    memories: tuple[StatusMemory, ...]
    checkpoints: tuple[StatusCheckpoint, ...]


@dataclass(frozen=True, slots=True)
class FrozenStatusFrame:
    """One authority-consistent current Context and optional recursive scope."""

    current_context_name: str
    profile_name: str
    contexts: tuple[FrozenStatusContext, ...]


@dataclass(frozen=True, slots=True)
class StatusContextResult:
    """Bounded public Status projection for one Context in the scope."""

    uid: str
    name: str
    source: SourceDisplayFacts
    memory_count: int
    memory_preview: tuple[StatusMemory, ...]
    checkpoint_count: int
    recent_checkpoints: tuple[StatusCheckpoint, ...]


@dataclass(frozen=True, slots=True)
class StatusResult:
    """Typed read-only Status result shared by presentation adapters."""

    current_context_name: str
    profile_name: str
    include_descendants: bool
    contexts: tuple[StatusContextResult, ...]

    @property
    def current(self) -> StatusContextResult:
        return self.contexts[0]


class StatusSourcePort(Protocol):
    """Freeze Status-visible Context, authority, relationship, and history facts."""

    def freeze(self, request: StatusRequest) -> FrozenStatusFrame:
        """Return one authority-consistent frame without terminal effects."""


def inspect_status(
    request: StatusRequest,
    *,
    source: StatusSourcePort,
) -> StatusResult:
    """Build a bounded inventory, preview, relationship, and history report."""

    if not isinstance(request, StatusRequest):
        raise TypeError("Status requires a StatusRequest.")
    frame = source.freeze(request)
    if not isinstance(frame, FrozenStatusFrame):
        raise StatusError("Status source returned an invalid frame.")
    if not frame.contexts:
        raise StatusError("Status source returned an empty Context scope.")
    if frame.contexts[0].name != frame.current_context_name:
        raise StatusError("Status source did not place the current Context first.")

    contexts = tuple(
        StatusContextResult(
            uid=context.uid,
            name=context.name,
            source=context.source,
            memory_count=len(context.memories),
            # The first persisted Memories are a stable preview, not a claim
            # that recently ordered content was recently changed.
            memory_preview=context.memories[:_MEMORY_PREVIEW_LIMIT],
            checkpoint_count=len(context.checkpoints),
            recent_checkpoints=context.checkpoints[:_RECENT_CHECKPOINT_LIMIT],
        )
        for context in frame.contexts
    )
    return StatusResult(
        current_context_name=frame.current_context_name,
        profile_name=frame.profile_name,
        include_descendants=request.include_descendants,
        contexts=contexts,
    )


__all__ = [
    "FrozenStatusContext",
    "FrozenStatusFrame",
    "NoCurrentStatusContextError",
    "StatusCheckpoint",
    "StatusContextResult",
    "StatusError",
    "StatusMemory",
    "StatusRequest",
    "StatusResult",
    "StatusSourcePort",
    "inspect_status",
]
