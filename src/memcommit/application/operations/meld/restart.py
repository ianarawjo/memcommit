"""Terminal-independent replacement contract for an existing Meld session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import MemoryRelationAnalysis
from memcommit.application.operations.meld.model import (
    INLINE_MELD_CONTEXT_NAME,
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MeldSession,
)
from memcommit.application.operations.meld.start import (
    MeldStartMode,
    MeldStartOrigin,
    validate_meld_start_scope,
)


class MeldRestartError(RuntimeError):
    """An existing Meld could not be replaced at its exact saved revision."""


@dataclass(frozen=True)
class MeldRestartRequest:
    """One explicit source pair and opaque target-session replacement token."""

    mode: MeldStartMode
    left_name: str
    right_name: str
    target_name: str
    expected_version: str
    left_descendants: bool = False
    right_descendants: bool = False
    incoming_memory: str | None = None
    baseline_memory: str | None = None
    incoming_text: str | None = None
    comparison: MemoryRelationAnalysis | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"SYMMETRIC", "DIRECTIONAL"}:
            raise MeldRestartError("Meld restart mode is invalid.")
        names = (self.left_name, self.right_name, self.target_name)
        if any(not isinstance(name, str) or not name for name in names):
            raise MeldRestartError("Meld restart Context names must be nonempty text.")
        if not isinstance(self.expected_version, str) or not self.expected_version:
            raise MeldRestartError("Meld restart requires an opaque saved version.")
        if not isinstance(self.left_descendants, bool) or not isinstance(
            self.right_descendants,
            bool,
        ):
            raise MeldRestartError("Meld descendant controls must be booleans.")
        validate_meld_start_scope(
            mode=self.mode,
            left_descendants=self.left_descendants,
            right_descendants=self.right_descendants,
            incoming_memory=self.incoming_memory,
            baseline_memory=self.baseline_memory,
            incoming_text=self.incoming_text,
            comparison=self.comparison,
            error_type=MeldRestartError,
        )
        if self.left_name == self.right_name:
            raise MeldRestartError("Meld sources must be distinct Contexts.")
        if (
            self.incoming_text is not None
            and self.left_name != INLINE_MELD_CONTEXT_NAME
        ):
            raise MeldRestartError(
                "Inline Meld Memory input requires the reserved INCOMING frame name."
            )
        if self.mode == "DIRECTIONAL" and self.target_name != self.right_name:
            raise MeldRestartError(
                "Directional Meld must use the existing BASELINE as target."
            )
        if self.mode == "SYMMETRIC" and self.target_name in {
            self.left_name,
            self.right_name,
        }:
            raise MeldRestartError(
                "Symmetric Meld sources and Result must be distinct Contexts."
            )


@dataclass(frozen=True)
class MeldRestartResult:
    """One completely replaced review and the origin of its semantic basis."""

    session: MeldSession
    origin: MeldStartOrigin


class MeldRestartPort(Protocol):
    def restart(
        self,
        request: MeldRestartRequest,
        *,
        provider_factory,
    ) -> MeldRestartResult:
        """Reauthorize, rebuild, and CAS-replace one complete Meld review."""


def run_meld_restart(
    request: MeldRestartRequest,
    *,
    port: MeldRestartPort,
    provider_factory,
) -> MeldRestartResult:
    """Replace a Meld without terminal, CLI, or TUI behavior."""

    if not isinstance(request, MeldRestartRequest):
        raise TypeError("Meld restart requires a MeldRestartRequest.")
    result = port.restart(request, provider_factory=provider_factory)
    session = result.session
    frame_names = tuple(frame.context_name for frame in session.frames)
    selected_memories = tuple(
        getattr(frame, "selected_memory_uid", None) for frame in session.frames
    )
    requested_memories = (request.incoming_memory, request.baseline_memory)
    memory_scope_matches = all(
        (selected is None if requested is None else (
            isinstance(selected, str) and selected.startswith(requested)
        ))
        for selected, requested in zip(
            selected_memories,
            requested_memories,
            strict=True,
        )
    )
    inline_scope_matches = request.incoming_text is None or (
        getattr(session, "schema_version", None)
        == MELD_INLINE_MEMORY_SCHEMA_VERSION
        and len(session.frames[0].memories) == 1
        and session.frames[0].memories[0].content == request.incoming_text
    )
    if (
        session.mode != request.mode
        or frame_names != (request.left_name, request.right_name)
        or session.target.context_name != request.target_name
        or not memory_scope_matches
        or not inline_scope_matches
        or session.state in {"APPLIED", "KEPT_REVIEW_ONLY"}
    ):
        raise MeldRestartError("Meld restart returned a session outside its request.")
    return result


__all__ = [
    "MeldRestartError",
    "MeldRestartPort",
    "MeldRestartRequest",
    "MeldRestartResult",
    "run_meld_restart",
]
