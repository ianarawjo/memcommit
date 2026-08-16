"""Stable public values for semantic Resolve analysis and Apply."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.resolve_application import ResolveAnalysis


@dataclass(frozen=True)
class ResolveEffectResult:
    kind: str
    memory_uid: str
    before: str | None
    after: str | None
    source_memory_uids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ResolveCandidateResult:
    uid: str
    summary: str
    effects: tuple[ResolveEffectResult, ...]
    verification_reason: str
    fit_reason: str
    deletes: int
    creates: int
    updates: int
    changed_units: int


@dataclass(frozen=True)
class ResolveAnalysisResult:
    context_name: str
    context_uid: str
    revision: str
    status: str
    initial_fit: str | None
    initial_fit_reason: str | None
    question: str
    requested_effects: tuple[str, ...]
    allowed_effects: tuple[str, ...]
    denied_effects: tuple[str, ...]
    candidates: tuple[ResolveCandidateResult, ...]
    _application_analysis: "ResolveAnalysis" = field(repr=False, compare=False)


@dataclass(frozen=True)
class ResolveApplyResult:
    context_name: str
    context_uid: str
    revision: str
    candidate_uid: str
    checkpoint_uid: str
    created_uids: tuple[str, ...]
    updated_uids: tuple[str, ...]
    deleted_uids: tuple[str, ...]


__all__ = [
    "ResolveAnalysisResult",
    "ResolveApplyResult",
    "ResolveCandidateResult",
    "ResolveEffectResult",
]
