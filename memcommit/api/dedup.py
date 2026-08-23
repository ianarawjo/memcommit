"""Stable public values for exact Dedup and semantic Dedun."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.dedup_application import FrozenDedupPlan


@dataclass(frozen=True)
class ExactDedupGroupResult:
    survivor_uid: str
    absorbed_uids: tuple[str, ...]
    content: str | None
    item_kind: str = "MEMORY"
    summary: str = ""


@dataclass(frozen=True)
class ExactDedupResult:
    context_name: str
    groups: tuple[ExactDedupGroupResult, ...]
    checkpoint_uid: str | None

    @property
    def removed_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class ExactDuplicateFindResult:
    """Read-only exact DUP report for one direct Context."""

    context_name: str
    memory_count: int
    groups: tuple[ExactDedupGroupResult, ...]
    item_count: int = 0

    @property
    def duplicate_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class DedunMemberResult:
    uid: str
    content: str
    ordinal: int
    recommended: bool


@dataclass(frozen=True)
class DedunEvidenceResult:
    finding_uid: str
    relation: str
    left_uid: str
    right_uid: str
    reason: str


@dataclass(frozen=True)
class DedunComponentResult:
    uid: str
    members: tuple[DedunMemberResult, ...]
    evidence: tuple[DedunEvidenceResult, ...]
    recommended_survivor_uid: str


@dataclass(frozen=True)
class DedunPlanResult:
    context_name: str
    context_uid: str
    revision: str
    components: tuple[DedunComponentResult, ...]
    exact_item_groups: tuple[ExactDedupGroupResult, ...]
    _application_plan: "FrozenDedupPlan" = field(repr=False, compare=False)


@dataclass(frozen=True)
class DedunApplyResult:
    context_name: str
    context_uid: str
    revision: str
    checkpoint_uid: str
    survivor_uids: tuple[str, ...]
    absorbed_uids: tuple[str, ...]


# Compatibility aliases for callers compiled against the former semantic
# Dedup/Consolidate public vocabulary.
DedupMemberResult = DedunMemberResult
DedupEvidenceResult = DedunEvidenceResult
DedupComponentResult = DedunComponentResult
DedupPlanResult = DedunPlanResult
DedupApplyResult = DedunApplyResult


__all__ = [
    "DedupApplyResult",
    "DedupComponentResult",
    "DedupEvidenceResult",
    "DedupMemberResult",
    "DedupPlanResult",
    "DedunApplyResult",
    "DedunComponentResult",
    "DedunEvidenceResult",
    "DedunMemberResult",
    "DedunPlanResult",
    "ExactDedupGroupResult",
    "ExactDedupResult",
    "ExactDuplicateFindResult",
]
