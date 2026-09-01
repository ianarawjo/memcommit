"""Immutable public projections for reviewed Meld sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MeldDecisionInput:
    """One explicit Resolve decision for a Meld Audit item."""

    issue_uid: str
    kind: Literal["confirm", "intent", "force"]
    intent: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.issue_uid, str) or not self.issue_uid.strip():
            raise ValueError("Meld decision issue_uid must be nonblank.")
        if self.kind not in {"confirm", "intent", "force"}:
            raise ValueError("Meld decision kind must be confirm, intent, or force.")
        if not isinstance(self.intent, str):
            raise TypeError("Meld decision intent must be text.")
        if self.kind == "intent" and not self.intent.strip():
            raise ValueError("An intent decision requires nonblank intent.")
        if self.kind != "intent" and self.intent:
            raise ValueError("Only an intent decision may carry intent text.")


@dataclass(frozen=True)
class MeldOptionResult:
    uid: str
    label: str
    text: str


@dataclass(frozen=True)
class MeldIssueResult:
    uid: str
    priority: str
    title: str
    question: str
    why_it_matters: str
    options: tuple[MeldOptionResult, ...]


@dataclass(frozen=True)
class MeldProposalResult:
    uid: str
    operation: str
    disposition: str
    content: str
    reason: str


@dataclass(frozen=True)
class MeldSessionResult:
    session_uid: str
    version: str
    mode: Literal["SYMMETRIC", "DIRECTIONAL"]
    state: str
    left_context: str
    right_context: str
    target_context: str
    turn_count: int
    overview: str | None
    ready_to_apply: bool
    issues: tuple[MeldIssueResult, ...]
    proposals: tuple[MeldProposalResult, ...]
    origin: str | None = None
    checkpoint_uid: str | None = None
    unresolved_count: int = 0


__all__ = [
    "MeldDecisionInput",
    "MeldIssueResult",
    "MeldOptionResult",
    "MeldProposalResult",
    "MeldSessionResult",
]
