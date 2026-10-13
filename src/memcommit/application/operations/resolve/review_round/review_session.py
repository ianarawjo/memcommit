"""Bind one Resolve review's starting analysis to its cumulative results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from memcommit.application.operations.merge.analysis.candidate import digest
from ..model import ResolveAnalysis


@dataclass(frozen=True)
class ResolveReviewSession:
    """One audited Context and its bound, cumulative review results."""

    analysis: ResolveAnalysis
    _frozen_digest: str | None = field(default=None, repr=False, compare=False)
    _prepared_results: dict = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __post_init__(self):
        if self.analysis.audit is None:
            raise ValueError("Issue review requires a completed Audit.")
        if self._frozen_digest is None:
            object.__setattr__(self, "_frozen_digest", self.digest)

    def require_unchanged(self):
        if self.digest != self._frozen_digest:
            raise ValueError("Resolve review input changed after preparation.")

    @property
    def digest(self):
        return digest(
            {
                "revision": self.analysis.frame.revision,
                "audit": self.analysis.audit.snapshot_digest,
                "issues": [asdict(issue) for issue in self.analysis.issues],
            }
        )

    def prepare_result(
        self,
        decisions,
        *,
        provider_factory=None,
        previous=None,
        reviewed_choices=None,
        chosen_candidate_uids=None,
    ):
        self.require_unchanged()
        from ..resolve_finalization.proposal import prepare_resolve_proposal

        def unavailable_provider():
            raise ValueError("Resolve instructions require a provider.")

        provider = (
            provider_factory if provider_factory is not None else unavailable_provider
        )
        result = prepare_resolve_proposal(
            self.analysis,
            decisions,
            update_provider_factory=provider,
            audit_provider_factory=provider,
            previous=previous,
            reviewed_choices=reviewed_choices,
            chosen_candidate_uids=chosen_candidate_uids,
        )
        result = replace(
            result,
            review_input=(previous.review_input if previous is not None else None)
            or self,
        )
        # Publication binds this exact output for both exact and semantic reviews.
        self._prepared_results[id(result)] = (result, result.digest, self.digest)
        return result

    def accept_reviewed_result(self, reviewed_input, result):
        """Keep later rounds bound to the original destination and its authority."""
        reviewed_input.validate_result(result)
        initial = result.initial_analysis or result.analysis
        if initial.frame.revision != self.analysis.frame.revision:
            raise ValueError("Resolve result belongs to another initial review.")
        self._prepared_results[id(result)] = (result, result.digest, self.digest)

    def validate_result(self, result):
        self.require_unchanged()
        retained = self._prepared_results.get(id(result))
        if (
            retained is None
            or retained[0] is not result
            or retained[1:] != (result.digest, self.digest)
        ):
            raise ValueError("Resolve result changed or belongs to another input.")
