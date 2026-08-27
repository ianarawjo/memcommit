"""Immutable public projections for conversational Atomize Grounding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AtomizeGroundingQuestionResult:
    """One current follow-up required or suggested by the saved dialogue."""

    uid: str
    kind: str
    priority: str
    text: str
    reason: str
    issue_uids: tuple[str, ...]


@dataclass(frozen=True)
class AtomizeGroundingProposalResult:
    """One exact current Memory edit or addition proposed by Grounding."""

    uid: str
    operation: str
    necessity: str
    memory_uid: str
    content: str
    reason: str
    issue_uids: tuple[str, ...]


@dataclass(frozen=True)
class AtomizeGroundingSessionResult:
    """Stable provider-free projection of one durable Grounding dialogue."""

    session_uid: str
    version: str
    context_name: str
    state: str
    issue_uid: str
    issue_kind: str
    arity: str
    turn_count: int
    active_understanding: tuple[str, ...]
    current_status: str | None
    current_explanation: str | None
    questions: tuple[AtomizeGroundingQuestionResult, ...]
    proposals: tuple[AtomizeGroundingProposalResult, ...]
    ready_to_apply: bool
    checkpoint_uid: str | None


@dataclass(frozen=True)
class AtomizeGroundingApplyResult:
    """Receipt for one applied or recovered complete Grounding proposal."""

    session: AtomizeGroundingSessionResult
    checkpoint_uid: str
    change_count: int
    recovered: bool


__all__ = [
    "AtomizeGroundingApplyResult",
    "AtomizeGroundingProposalResult",
    "AtomizeGroundingQuestionResult",
    "AtomizeGroundingSessionResult",
]
