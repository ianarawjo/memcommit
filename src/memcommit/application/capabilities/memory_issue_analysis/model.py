"""Typed Memory Issue findings and read-only analysis reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    ExactDuplicateGroup,
)
from memcommit.core.context import Memory


QUALITY_RULESET_VERSIONS = {
    "find_duplicates": "duplicates-v1-draft",
    "find_ambiguities": "ambiguity-v1-draft",
    "find_conflicts": "conflict-v2-draft",
}

DuplicateRelation = Literal[
    "EXACT",
    "SURFACE_EQUIVALENT",
    "SEMANTIC_EQUIVALENT",
]
Interpretation = Literal["SINGLE", "DOMINANT", "COMPETING"]
Clarification = Literal["NONE", "HELPFUL", "REQUIRED"]
ConflictLabel = Literal["YES", "MAY"]


class FindingsError(RuntimeError):
    """Safe, user-facing error from a semantic finding operation."""


class FindingsProvider(Protocol):
    """One-shot structured provider used by Memory Issue detection."""

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one structured model completion."""


@dataclass(frozen=True)
class DuplicateFinding:
    left: Memory
    right: Memory
    relation: DuplicateRelation
    reason: str

    def __post_init__(self) -> None:
        # Negative calibration boundaries are never positive cleanup evidence.
        # Reject them at the typed edge so a fixture or adapter cannot render an
        # OVERLAP/UNKNOWN/DISTINCT pair as a removable redundancy.
        if self.relation not in {
            "EXACT",
            "SURFACE_EQUIVALENT",
            "SEMANTIC_EQUIVALENT",
        }:
            raise ValueError("Duplicate finding requires a positive DUN relation.")


@dataclass(frozen=True)
class AmbiguityFinding:
    memory: Memory
    interpretation: Interpretation
    clarification: Clarification
    ordinary_readings: tuple[str, ...]
    reason: str
    question: str


@dataclass(frozen=True)
class ConflictFinding:
    left: Memory
    right: Memory
    conflict: ConflictLabel
    reason: str
    question: str


@dataclass(frozen=True)
class DuplicateReport:
    memory_count: int
    findings: tuple[DuplicateFinding, ...]
    exact_item_groups: tuple[ExactDuplicateGroup, ...] = ()

    @property
    def exact_findings(self) -> tuple[DuplicateFinding, ...]:
        """Return deterministic DUP evidence inside the complete DUN report."""

        return tuple(
            finding for finding in self.findings if finding.relation == "EXACT"
        )

    @property
    def semantic_findings(self) -> tuple[DuplicateFinding, ...]:
        """Return differently stored semantic-DUN evidence."""

        return tuple(
            finding for finding in self.findings if finding.relation != "EXACT"
        )

    @property
    def group_count(self) -> int:
        return _duplicate_group_count(self.findings) + len(self.exact_item_groups)

    @property
    def exact_group_count(self) -> int:
        return _duplicate_group_count(self.exact_findings) + len(
            self.exact_item_groups
        )

    @property
    def semantic_group_count(self) -> int:
        return _duplicate_group_count(self.semantic_findings)

    @property
    def exact_duplicate_count(self) -> int:
        return len(self.exact_findings) + sum(
            group.duplicate_count for group in self.exact_item_groups
        )

    @property
    def semantic_redundancy_count(self) -> int:
        return len(self.semantic_findings)

    @property
    def redundancy_count(self) -> int:
        # The analyzer emits a forest: each evidence edge adds exactly one
        # redundant member to its connected DUN group.
        return len(self.findings) + sum(
            group.duplicate_count for group in self.exact_item_groups
        )


@dataclass(frozen=True)
class AmbiguityReport:
    memory_count: int
    findings: tuple[AmbiguityFinding, ...]


@dataclass(frozen=True)
class ConflictReport:
    memory_count: int
    pair_count: int
    findings: tuple[ConflictFinding, ...]


def _duplicate_group_count(findings: tuple[DuplicateFinding, ...]) -> int:
    """Count connected evidence components without interpreting relation type."""

    if not findings:
        return 0
    parent: dict[str, str] = {}

    def root(uid: str) -> str:
        parent.setdefault(uid, uid)
        while parent[uid] != uid:
            parent[uid] = parent[parent[uid]]
            uid = parent[uid]
        return uid

    for finding in findings:
        left_root = root(finding.left.uid)
        right_root = root(finding.right.uid)
        if left_root != right_root:
            parent[right_root] = left_root
    return len({root(uid) for uid in parent})


__all__ = [
    "AmbiguityFinding",
    "AmbiguityReport",
    "Clarification",
    "ConflictFinding",
    "ConflictLabel",
    "ConflictReport",
    "DuplicateFinding",
    "DuplicateRelation",
    "DuplicateReport",
    "FindingsError",
    "FindingsProvider",
    "Interpretation",
    "QUALITY_RULESET_VERSIONS",
]
