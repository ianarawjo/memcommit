"""Terminal-independent construction contract for new Meld sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.operations.compare.ledger.model import ComparisonAnalysis
from memcommit.meld import (
    INLINE_MELD_CONTEXT_NAME,
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MELD_TEXT_LIMIT,
    MeldSession,
)


MeldStartMode = Literal["SYMMETRIC", "DIRECTIONAL"]
MeldStartOrigin = Literal[
    "PROVIDER",
    "SAVED_COMPARISON",
    "EXACT_PREWARM",
    "EQUIVALENT_SCOPE_PREWARM",
    "PROJECTED_PREWARM",
]


class MeldStartError(RuntimeError):
    """A new Meld could not safely reach a durable reviewed session."""


def validate_meld_start_scope(
    *,
    mode: MeldStartMode,
    left_descendants: bool,
    right_descendants: bool,
    incoming_memory: str | None,
    baseline_memory: str | None,
    incoming_text: str | None,
    comparison: ComparisonAnalysis | None,
    error_type: type[RuntimeError],
) -> None:
    """Validate directional Memory focus before any Store or provider work."""

    selectors = (incoming_memory, baseline_memory)
    if any(
        selector is not None
        and (not isinstance(selector, str) or not selector.strip())
        for selector in selectors
    ):
        raise error_type("Meld Memory selectors must be nonempty text.")
    if mode != "DIRECTIONAL" and any(selector is not None for selector in selectors):
        raise error_type("Only directional Meld supports direct-Memory focus.")
    if incoming_memory is not None and left_descendants:
        raise error_type(
            "INCOMING Memory focus cannot be combined with descendants."
        )
    if baseline_memory is not None and right_descendants:
        raise error_type(
            "BASELINE Memory focus cannot be combined with descendants."
        )
    if comparison is not None and any(selector is not None for selector in selectors):
        raise error_type(
            "Meld Memory focus cannot reuse a whole-frame Compare analysis."
        )
    if incoming_text is not None:
        if not isinstance(incoming_text, str) or not incoming_text.strip():
            raise error_type("Inline Meld Memory content must be nonempty text.")
        if len(incoming_text) > MELD_TEXT_LIMIT:
            raise error_type("Inline Meld Memory content is too long.")
        if mode != "DIRECTIONAL":
            raise error_type("Only directional Meld supports inline Memory input.")
        if left_descendants or incoming_memory is not None or comparison is not None:
            raise error_type(
                "Inline Meld Memory input cannot be combined with INCOMING "
                "descendants, an INCOMING Memory selector, or Compare evidence."
            )


@dataclass(frozen=True)
class MeldStartRequest:
    """One canonical source pair and target contract, independent of argv."""

    mode: MeldStartMode
    left_name: str
    right_name: str
    target_name: str
    left_descendants: bool = False
    right_descendants: bool = False
    create_target: bool = False
    incoming_memory: str | None = None
    baseline_memory: str | None = None
    incoming_text: str | None = None
    comparison: ComparisonAnalysis | None = None

    def __post_init__(self) -> None:
        names = (self.left_name, self.right_name, self.target_name)
        if self.mode not in {"SYMMETRIC", "DIRECTIONAL"}:
            raise MeldStartError("Meld start mode is invalid.")
        if any(not isinstance(name, str) or not name for name in names):
            raise MeldStartError("Meld start Context names must be nonempty text.")
        if not isinstance(self.left_descendants, bool) or not isinstance(
            self.right_descendants,
            bool,
        ):
            raise MeldStartError("Meld descendant controls must be booleans.")
        if not isinstance(self.create_target, bool):
            raise MeldStartError("Meld create_target must be a boolean.")
        validate_meld_start_scope(
            mode=self.mode,
            left_descendants=self.left_descendants,
            right_descendants=self.right_descendants,
            incoming_memory=self.incoming_memory,
            baseline_memory=self.baseline_memory,
            incoming_text=self.incoming_text,
            comparison=self.comparison,
            error_type=MeldStartError,
        )
        if self.left_name == self.right_name:
            raise MeldStartError("Meld sources must be distinct Contexts.")
        if (
            self.incoming_text is not None
            and self.left_name != INLINE_MELD_CONTEXT_NAME
        ):
            raise MeldStartError(
                "Inline Meld Memory input requires the reserved INCOMING frame name."
            )
        if self.mode == "DIRECTIONAL":
            if self.target_name != self.right_name or self.create_target:
                raise MeldStartError(
                    "Directional Meld must use the existing BASELINE as target."
                )
        elif self.target_name in {self.left_name, self.right_name}:
            raise MeldStartError(
                "Symmetric Meld sources and Result must be distinct Contexts."
            )


@dataclass(frozen=True)
class MeldStartResult:
    """One durable initial review and the origin of its semantic basis."""

    session: MeldSession
    origin: MeldStartOrigin
    created_target: bool


class MeldStartPort(Protocol):
    def start(
        self,
        request: MeldStartRequest,
        *,
        provider_factory,
    ) -> MeldStartResult:
        """Authorize, analyze or reuse, and publish one complete start."""


def run_meld_start(
    request: MeldStartRequest,
    *,
    port: MeldStartPort,
    provider_factory,
) -> MeldStartResult:
    """Start a Meld without terminal, CLI, or TUI behavior."""

    if not isinstance(request, MeldStartRequest):
        raise TypeError("Meld start requires a MeldStartRequest.")
    result = port.start(request, provider_factory=provider_factory)
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
        or result.created_target != request.create_target
        or not memory_scope_matches
        or not inline_scope_matches
        or session.state in {"APPLIED", "KEPT_REVIEW_ONLY"}
    ):
        raise MeldStartError("Meld start returned a session outside its request.")
    return result


__all__ = [
    "MeldStartError",
    "MeldStartMode",
    "MeldStartOrigin",
    "MeldStartPort",
    "MeldStartRequest",
    "MeldStartResult",
    "run_meld_start",
    "validate_meld_start_scope",
]
