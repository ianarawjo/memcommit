"""Terminal-independent construction contract for new Meld sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.comparison import ComparisonAnalysis
from memcommit.meld import MeldSession


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
        if self.left_name == self.right_name:
            raise MeldStartError("Meld sources must be distinct Contexts.")
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
    if (
        session.mode != request.mode
        or frame_names != (request.left_name, request.right_name)
        or session.target.context_name != request.target_name
        or result.created_target != request.create_target
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
]
