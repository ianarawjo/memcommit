"""Stable public values for semantic Dedun planning and Apply."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from memcommit.adapters.python_api.dedup import ExactDedupGroupResult

if TYPE_CHECKING:
    from memcommit.application.operations.dedun.application import FrozenDedunPlan


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
    _application_plan: "FrozenDedunPlan" = field(repr=False, compare=False)


@dataclass(frozen=True)
class DedunApplyResult:
    context_name: str
    context_uid: str
    revision: str
    checkpoint_uid: str
    survivor_uids: tuple[str, ...]
    absorbed_uids: tuple[str, ...]


# Preserve only the established public aliases; canonical code uses Dedun names.
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
]
