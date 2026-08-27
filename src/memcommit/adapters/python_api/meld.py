"""Immutable public projections for reviewed Meld sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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


@dataclass(frozen=True)
class MeldApplyResult:
    session: MeldSessionResult
    recovered: bool
    checkpoint_uid: str
    result_count: int


__all__ = [
    "MeldApplyResult",
    "MeldIssueResult",
    "MeldOptionResult",
    "MeldProposalResult",
    "MeldSessionResult",
]
