"""Stable public values for semantic Resolve analysis and Apply."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.application.operations.resolve.application import ResolveAnalysis


@dataclass(frozen=True)
class ResolveIssueResult:
    uid: str
    audit_key: str
    kind: str
    classification: str
    memory_uids: tuple[str, ...]
    proposed_direction: str
    reason: str
    question: str


@dataclass(frozen=True)
class ResolveDecisionInput:
    """One public finalized response to an Issue returned by Resolve."""

    issue_uid: str
    kind: str
    intent: str = ""


@dataclass(frozen=True)
class ResolveAnalysisResult:
    context_name: str
    context_uid: str
    revision: str
    status: str
    question: str
    requested_effects: tuple[str, ...]
    allowed_effects: tuple[str, ...]
    denied_effects: tuple[str, ...]
    issues: tuple[ResolveIssueResult, ...]
    _application_analysis: "ResolveAnalysis" = field(repr=False, compare=False)


@dataclass(frozen=True)
class ResolveApplyResult:
    context_name: str
    context_uid: str
    revision: str
    plan_uid: str
    checkpoint_uid: str
    created_uids: tuple[str, ...]
    updated_uids: tuple[str, ...]
    deleted_uids: tuple[str, ...]
    unresolved_issue_uids: tuple[str, ...] = ()


__all__ = [
    "ResolveAnalysisResult",
    "ResolveApplyResult",
    "ResolveDecisionInput",
    "ResolveIssueResult",
]
