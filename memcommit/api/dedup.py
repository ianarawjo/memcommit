"""Stable public values for deterministic Dedup planning and Apply."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.dedup_application import FrozenDedupPlan


@dataclass(frozen=True)
class DedupMemberResult:
    uid: str
    content: str
    ordinal: int
    recommended: bool


@dataclass(frozen=True)
class DedupEvidenceResult:
    finding_uid: str
    relation: str
    left_uid: str
    right_uid: str
    reason: str


@dataclass(frozen=True)
class DedupComponentResult:
    uid: str
    members: tuple[DedupMemberResult, ...]
    evidence: tuple[DedupEvidenceResult, ...]
    recommended_survivor_uid: str


@dataclass(frozen=True)
class DedupPlanResult:
    context_name: str
    context_uid: str
    revision: str
    components: tuple[DedupComponentResult, ...]
    _application_plan: "FrozenDedupPlan" = field(repr=False, compare=False)


@dataclass(frozen=True)
class DedupApplyResult:
    context_name: str
    context_uid: str
    revision: str
    checkpoint_uid: str
    survivor_uids: tuple[str, ...]
    absorbed_uids: tuple[str, ...]


__all__ = [
    "DedupApplyResult",
    "DedupComponentResult",
    "DedupEvidenceResult",
    "DedupMemberResult",
    "DedupPlanResult",
]
