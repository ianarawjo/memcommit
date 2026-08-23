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
    context_name: str | None = None


@dataclass(frozen=True)
class ExactDedupContextResult:
    """One direct Context effect inside an exact-Dedup scope."""

    context_name: str
    groups: tuple[ExactDedupGroupResult, ...]
    checkpoint_uid: str | None

    @property
    def removed_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class ExactDedupResult:
    context_name: str
    groups: tuple[ExactDedupGroupResult, ...]
    checkpoint_uid: str | None
    include_descendants: bool = False
    contexts: tuple[ExactDedupContextResult, ...] = ()
    checkpoint_uids: tuple[str, ...] = ()
    operation_uid: str | None = None

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
    include_descendants: bool = False
    contexts: tuple["ExactDuplicateContextResult", ...] = ()

    @property
    def duplicate_count(self) -> int:
        return sum(len(group.absorbed_uids) for group in self.groups)


@dataclass(frozen=True)
class ExactDuplicateContextResult:
    """Read-only exact groups for one independently judged direct Context."""

    context_name: str
    context_uid: str
    memory_count: int
    item_count: int
    groups: tuple[ExactDedupGroupResult, ...]

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
    "ExactDedupContextResult",
    "ExactDedupResult",
    "ExactDuplicateContextResult",
    "ExactDuplicateFindResult",
]
