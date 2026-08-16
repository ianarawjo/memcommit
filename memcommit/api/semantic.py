"""Stable public values for Fit, Distill, and Elaborate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.distill_application import DistillResult as ApplicationDistillResult
    from memcommit.fit_store import GroundFitReceipt
    from memcommit.ground_distill import GroundDistillResult
    from memcommit.ground_elaborate import GroundElaborateResult
    from memcommit.ground_resolution import GroundResolutionPlan


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
    _ground_result: GroundDistillResult | None = field(
        default=None,
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


@dataclass(frozen=True)
class ElaborateCaseProposal:
    uid: str
    proposition: str
    expected: str
    rationale: str
    case_role: str
    source_rule_index: int


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
    _ground_result: GroundElaborateResult | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class GroundFitJudgmentResult:
    example_uid: str
    example_alias: str
    proposition: str
    status: str
    reason: str
    rule_uids: tuple[str, ...]


@dataclass(frozen=True)
class GroundFitReceiptResult:
    receipt_uid: str
    receipt_digest: str
    ground_uid: str
    ground_name: str
    ground_revision: int
    ground_digest: str
    overview: str
    current: bool
    judgments: tuple[GroundFitJudgmentResult, ...]
    _receipt: GroundFitReceipt = field(repr=False, compare=False)


@dataclass(frozen=True)
class GroundResolutionActionResult:
    kind: str
    content: str
    rationale: str
    selector: str
    source_item_uid: str
    case_role: str
    use: str
    rule_provenance: str


@dataclass(frozen=True)
class GroundResolutionPlanResult:
    plan_digest: str
    artifact_kind: str
    artifact_uid: str
    artifact_digest: str
    source_verification: str
    candidate_verification: str
    ground_uid: str
    ground_name: str
    ground_revision: int
    ground_digest: str
    explanation: str
    action: GroundResolutionActionResult
    _plan: GroundResolutionPlan = field(repr=False, compare=False)
    _artifact: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class GroundResolutionApplyResult:
    plan_digest: str
    artifact_uid: str
    action_kind: str
    previous_revision: int
    resulting_revision: int
    resulting_ground_digest: str
    mutated: bool


__all__ = [
    "DistillApplyResult",
    "DistillProposal",
    "DistillRuleProposal",
    "ElaborateCaseProposal",
    "ElaborateProposal",
    "ElaborateRuleProposal",
    "FitJudgmentResult",
    "FitPropositionInput",
    "GroundFitJudgmentResult",
    "GroundFitReceiptResult",
    "GroundResolutionActionResult",
    "GroundResolutionApplyResult",
    "GroundResolutionPlanResult",
]
