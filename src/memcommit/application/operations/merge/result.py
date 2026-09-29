"""Retain verified phase results and join them into one publishable Merge result."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

from memcommit.application.operations.resolve.proposal import ResolveProposal
from memcommit.core.context import Context

from .analysis.candidate import digest
from .analysis.choices import (
    MergeConflictAnalysis,
    MergeDecisionSet,
    finalize_merge_decisions,
)
from .analysis.materialization import materialize_structural_result
from .inputs import StructuralResolutionInput
from .records import LiteralMergeRound
from .target_policy import MergeTargetPolicy, validate_target_result


@dataclass(frozen=True)
class LiteralMergeReview:
    """One structural Merge analysis and its bound, verified choice results."""

    analysis: MergeConflictAnalysis
    structural_input: StructuralResolutionInput
    target_policy: MergeTargetPolicy | None = None
    input_digest: str | None = None
    defer_target_validation: bool = False
    _frozen_digest: str | None = field(default=None, repr=False, compare=False)
    _prepared_results: dict = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __post_init__(self):
        if self.target_policy is not None and self.structural_input is None:
            raise ValueError("A Target policy requires its original structural input.")
        if (
            self.structural_input is not None
            and self.structural_input.revision != self.analysis.revision
        ):
            raise ValueError("Structural review input belongs to another revision.")

        if self._frozen_digest is None:
            object.__setattr__(self, "_frozen_digest", self.digest)

    def require_unchanged(self):
        if self.digest != self._frozen_digest:
            raise ValueError("Merge review input changed after preparation.")

    @property
    def digest(self):
        return digest(
            {
                "input": self.input_digest,
                "deferred": self.defer_target_validation,
                "revision": self.analysis.revision,
                "report": asdict(self.analysis.report),
                "issues": [asdict(issue) for issue in self.analysis.review_issues],
                "policy": {
                    "effects": self.target_policy.allowed_effects,
                    "mutable": self.target_policy.context_mutable,
                    "protected": sorted(self.target_policy.protected_uids),
                }
                if self.target_policy
                else None,
                "structural": asdict(self.structural_input)
                if self.structural_input
                else None,
            }
        )

    def prepare_result(self, decisions):
        self.require_unchanged()
        result = prepare_literal_result(self.analysis, decisions, self.structural_input)
        result = replace(result, review_input=self)
        if not self.defer_target_validation:
            validate_target_result(
                self.target_policy, self.structural_input.target(), result.post_image
            )
        self._prepared_results[id(result)] = (result, result.digest, self.digest)
        return result

    def validate_result(self, result):
        self.require_unchanged()
        retained = self._prepared_results.get(id(result))
        if (
            retained is None
            or retained[0] is not result
            or retained[1:] != (result.digest, self.digest)
        ):
            raise ValueError("Resolve result changed or belongs to another input.")


@dataclass(frozen=True, slots=True)
class LiteralMergeResult:
    analysis: MergeConflictAnalysis
    decisions: MergeDecisionSet
    target: Context
    post_image: Context
    round: LiteralMergeRound
    review_input: LiteralMergeReview | None = field(
        default=None, repr=False, compare=False
    )

    @property
    def digest(self):
        return digest(
            dict(
                revision=self.analysis.revision,
                target=self.target.to_dict(),
                post_image=self.post_image.to_dict(),
                round=self.round.to_dict(),
            )
        )


def prepare_literal_result(analysis, decisions, structural_input):
    finalized = finalize_merge_decisions(analysis, decisions)
    post_image, mappings = materialize_structural_result(
        analysis, finalized, structural_input
    )
    round = LiteralMergeRound(
        analysis.candidate,
        analysis.report,
        analysis.review_issues,
        finalized,
        analysis.candidate.context(),
        post_image,
        input_result_uids=mappings,
    )
    return LiteralMergeResult(
        analysis=analysis,
        decisions=finalized,
        target=structural_input.target(),
        post_image=post_image,
        round=round,
    )


@dataclass(frozen=True, slots=True)
class MergeResult:
    literal: LiteralMergeResult
    semantic: ResolveProposal | None = None

    @property
    def target(self):
        return self.literal.target

    @property
    def post_image(self):
        return self.semantic.post_image if self.semantic else self.literal.post_image

    @property
    def rounds(self):
        return (self.literal.round,) + (self.semantic.rounds if self.semantic else ())

    @property
    def post_audit(self):
        return self.semantic.post_audit if self.semantic else None

    @property
    def forced_audit_keys(self):
        return self.semantic.forced_audit_keys if self.semantic else ()

    @property
    def unresolved_issue_uids(self):
        return self.semantic.unresolved_issue_uids if self.semantic else ()

    @property
    def digest(self):
        return digest(
            dict(
                literal=self.literal.digest,
                semantic=self.semantic.digest if self.semantic else None,
            )
        )

    def validate(self, prepared):
        self._validate_components(prepared)
        self.literal.review_input.validate_result(self)

    def _validate_components(self, prepared):
        prepared.require_unchanged()
        review = self.literal.review_input
        if review is None or review.input_digest != prepared.literal_input.digest:
            raise ValueError("Literal result belongs to another Merge input.")
        review.validate_result(self.literal)
        if prepared.request.method == "LITERAL":
            if self.semantic is not None:
                raise ValueError("Literal Merge cannot include semantic decisions.")
        else:
            semantic = self.semantic
            if (
                semantic is None
                or not semantic.ready_to_apply
                or semantic.post_audit is None
            ):
                raise ValueError(
                    "Semantic Merge requires its completed Resolve result."
                )
            if semantic.review_input is None:
                raise ValueError("Resolve result requires its original review binding.")
            semantic.review_input.validate_result(semantic)
            if (
                semantic.target.to_dict() != self.literal.post_image.to_dict()
                or (semantic.initial_analysis or semantic.analysis).frame.revision
                != self.literal.digest
            ):
                raise ValueError("Resolve result is not bound to this Literal result.")
        # Semantic staging may use permissions unavailable at the destination.
        # Validate the composed effect against the real Target before Preview/Apply.
        validate_target_result(
            review.target_policy, review.structural_input.target(), self.post_image
        )


def finish_merge(prepared, literal, semantic=None):
    result = MergeResult(literal, semantic)
    result._validate_components(prepared)
    review = literal.review_input
    review._prepared_results[id(result)] = (result, result.digest, review.digest)
    return result
