"""Stable public values for Fit, Distill, and Makemore."""

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
class MakemoreRuleProposal:
    uid: str
    content: str
    rationale: str
    target_context_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class MakemoreRuleCheckProposal:
    source_rule_index: int
    evidence: str


@dataclass(frozen=True)
class MakemoreCaseValidationProposal:
    source_fit: str
    source_fit_reason: str
    rule_conformance: str
    conforming_source_rule_indexes: tuple[int, ...]


@dataclass(frozen=True)
class MakemoreCaseProposal:
    uid: str
    proposition: str
    expected: str
    rationale: str
    case_role: str
    rule_checks: tuple[MakemoreRuleCheckProposal, ...]
    validation: MakemoreCaseValidationProposal | None
    target_context_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class MakemoreTargetContextItemProposal:
    alias: str
    kind: str
    context_name: str
    memory_uid: str | None
    content: str | None


@dataclass(frozen=True)
class MakemoreProposal:
    analysis_uid: str
    mode: str
    inputs: tuple[str, ...]
    overview: str
    rules: tuple[MakemoreRuleProposal, ...]
    cases: tuple[MakemoreCaseProposal, ...]
    origin: str
    verification: str = "UNVERIFIED"
    quality_policy: str = "BEST_EFFORT"
    target_context_name: str | None = None
    target_context_items: tuple[MakemoreTargetContextItemProposal, ...] = ()


__all__ = [
    "DistillApplyResult",
    "DistillProposal",
    "DistillRuleProposal",
    "MakemoreCaseProposal",
    "MakemoreCaseValidationProposal",
    "MakemoreProposal",
    "MakemoreRuleCheckProposal",
    "MakemoreRuleProposal",
    "MakemoreTargetContextItemProposal",
    "FitJudgmentResult",
    "FitPropositionInput",
]
