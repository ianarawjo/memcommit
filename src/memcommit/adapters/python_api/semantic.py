"""Stable public values for Fit, Distill, and Elaborate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.application.operations.distill.application import (
        DistillResult as ApplicationDistillResult,
    )


@dataclass(frozen=True)
class FitPropositionInput:
    """One public Fit constraint with optional stable alias and semantic role."""

    content: str
    role: str = "PROPOSITION"
    alias: str | None = None


@dataclass(frozen=True)
class FitJudgmentResult:
    """One read-only set-level YES/MAY/NO compatibility judgment."""

    analysis_uid: str
    verdict: str
    reason: str
    propositions: tuple[FitPropositionInput, ...]
    background: tuple[FitPropositionInput, ...]
    considered_aliases: tuple[str, ...]
    material_aliases: tuple[str, ...]
    consistent_reading: str
    inconsistent_reading: str


@dataclass(frozen=True)
class DistillRuleProposal:
    uid: str
    content: str
    rationale: str
    support_memory_uids: tuple[str, ...]
    boundary_memory_uids: tuple[str, ...]


@dataclass(frozen=True)
class DistillProposal:
    analysis_uid: str
    source_context: str
    source_digest: str
    goal: str | None
    overview: str
    rules: tuple[DistillRuleProposal, ...]
    outside_memory_uids: tuple[str, ...]
    origin: str
    apply_allowed: bool
    _application_result: ApplicationDistillResult = field(
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class DistillApplyResult:
    output_name: str
    output_context_uid: str
    checkpoint_uid: str
    result_memory_uids: tuple[str, ...]


@dataclass(frozen=True)
class ElaborateRuleProposal:
    uid: str
    content: str
    rationale: str
    target_context_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ElaborateRuleCheckProposal:
    source_rule_index: int
    evidence: str


@dataclass(frozen=True)
class ElaborateCaseValidationProposal:
    source_fit: str
    source_fit_reason: str
    rule_conformance: str
    conforming_source_rule_indexes: tuple[int, ...]


@dataclass(frozen=True)
class ElaborateCaseProposal:
    uid: str
    proposition: str
    expected: str
    rationale: str
    case_role: str
    rule_checks: tuple[ElaborateRuleCheckProposal, ...]
    validation: ElaborateCaseValidationProposal | None
    target_context_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ElaborateTargetContextItemProposal:
    alias: str
    kind: str
    context_name: str
    memory_uid: str | None
    content: str | None


@dataclass(frozen=True)
class ElaborateProposal:
    analysis_uid: str
    mode: str
    inputs: tuple[str, ...]
    overview: str
    rules: tuple[ElaborateRuleProposal, ...]
    cases: tuple[ElaborateCaseProposal, ...]
    origin: str
    verification: str = "UNVERIFIED"
    quality_policy: str = "BEST_EFFORT"
    target_context_name: str | None = None
    target_context_items: tuple[ElaborateTargetContextItemProposal, ...] = ()


__all__ = [
    "DistillApplyResult",
    "DistillProposal",
    "DistillRuleProposal",
    "ElaborateCaseProposal",
    "ElaborateCaseValidationProposal",
    "ElaborateProposal",
    "ElaborateRuleCheckProposal",
    "ElaborateRuleProposal",
    "ElaborateTargetContextItemProposal",
    "FitJudgmentResult",
    "FitPropositionInput",
]
