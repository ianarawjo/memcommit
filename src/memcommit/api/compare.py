"""Immutable public projections for read-only Compare analyses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComparisonFrameResult:
    uid: str
    side: str
    context_name: str
    memory_uids: tuple[str, ...]
    selected_memory_uid: str | None


@dataclass(frozen=True)
class ComparisonMemberResult:
    frame_uid: str
    memory_uid: str


@dataclass(frozen=True)
class ComparisonRelationResult:
    uid: str
    kind: str
    status: str
    members: tuple[ComparisonMemberResult, ...]
    summary: str
    reason: str


@dataclass(frozen=True)
class ComparisonOptionResult:
    uid: str
    label: str
    text: str


@dataclass(frozen=True)
class ComparisonIssueResult:
    uid: str
    relation_uids: tuple[str, ...]
    priority: str
    title: str
    question: str
    why_it_matters: str
    options: tuple[ComparisonOptionResult, ...]


@dataclass(frozen=True)
class ComparisonReportsResult:
    both: str
    differences: str
    reference_only: str
    compared_only: str


@dataclass(frozen=True)
class ComparisonResult:
    """One complete read-only analysis or ephemeral authorized projection."""

    analysis_uid: str
    version: str
    ruleset_version: str
    frames: tuple[ComparisonFrameResult, ComparisonFrameResult]
    include_descendants: tuple[bool, bool]
    overview: str
    reports: ComparisonReportsResult | None
    relations: tuple[ComparisonRelationResult, ...]
    issues: tuple[ComparisonIssueResult, ...]
    origin: str
    durable: bool
    retention: str | None


__all__ = [
    "ComparisonFrameResult",
    "ComparisonIssueResult",
    "ComparisonMemberResult",
    "ComparisonOptionResult",
    "ComparisonRelationResult",
    "ComparisonReportsResult",
    "ComparisonResult",
]
