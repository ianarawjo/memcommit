"""Frozen review-round evidence and next-round analysis, without terminal I/O."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace

from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.core.context import Context

from memcommit.application.capabilities.resolution.workbench import ResolutionOption
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.update.model.changes import (
    UpdateOperation,
    _operation_from_dict,
)
from .application import analyze_resolve_audit
from .model import ResolveAnalysis, ResolveIssue
from .decisions import ResolveDecision, ResolveDecisionSet, resolution_input_uid
from .resolution_options.generation import ProviderResolveOptionsPort


@dataclass(frozen=True)
class ResolveReviewInput:
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
        frame_port=None,
        previous=None,
        reviewed_choices=None,
    ):
        self.require_unchanged()
        from .detached import DetachedResolvePort
        from .proposal import prepare_resolve_proposal

        def unavailable_provider():
            raise ValueError("Resolve instructions require a provider.")

        provider = (
            provider_factory if provider_factory is not None else unavailable_provider
        )
        result = prepare_resolve_proposal(
            self.analysis,
            decisions,
            frame_port=frame_port
            if frame_port is not None
            else DetachedResolvePort(
                self.analysis.audit.source, revision=self.analysis.frame.revision
            ),
            update_provider_factory=provider,
            audit_provider_factory=provider,
            previous=previous,
            reviewed_choices=reviewed_choices,
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


@dataclass(frozen=True, slots=True)
class IssueReviewRound:
    """Review evidence shared by live Preview/lineage and decoded History."""

    audit: QualityAuditSession
    issues: tuple[ResolveIssue, ...]
    decisions: ResolveDecisionSet
    _before: Context = field(repr=False)
    _after: Context = field(repr=False)
    effects: tuple[UpdateOperation, ...] = ()
    input_result_uids: tuple[tuple[str, str], ...] | None = None

    def __post_init__(self):
        # Context is mutable. Own detached snapshots and expose copies so a
        # later round or Preview cannot rewrite already reviewed evidence.
        object.__setattr__(self, "_before", deepcopy(self._before))
        object.__setattr__(self, "_after", deepcopy(self._after))

    def before(self) -> Context:
        return deepcopy(self._before)

    def after(self) -> Context:
        return deepcopy(self._after)

    def to_dict(self):
        return dict(
            audit=self.audit.to_dict(),
            issues=[asdict(issue) for issue in self.issues],
            decisions=[asdict(decision) for decision in self.decisions.decisions],
            before=self._before.to_dict(),
            after=self._after.to_dict(),
            effects=[effect.to_dict() for effect in self.effects],
            input_result_uids=list(self.input_result_uids)
            if self.input_result_uids is not None
            else None,
        )

    @classmethod
    def from_dict(cls, value):
        """Decode persisted round evidence once, at the History read boundary."""
        if not isinstance(value, dict) or set(value) != {
            "audit",
            "issues",
            "decisions",
            "before",
            "after",
            "effects",
            "input_result_uids",
            "revision",
        }:
            raise ValueError("Invalid Issue Review round.")
        issues = tuple(
            ResolveIssue(
                **(
                    issue
                    | {
                        "item_uids": tuple(issue["item_uids"]),
                        "choices": tuple(
                            ResolutionOption(**choice) for choice in issue["choices"]
                        ),
                    }
                )
            )
            for issue in value["issues"]
        )
        return cls(
            QualityAuditSession.from_dict(value["audit"]),
            issues,
            ResolveDecisionSet(
                value["revision"],
                tuple(ResolveDecision(**decision) for decision in value["decisions"]),
            ),
            Context.from_dict(value["before"]),
            Context.from_dict(value["after"]),
            tuple(_operation_from_dict(effect) for effect in value["effects"]),
            None
            if value["input_result_uids"] is None
            else tuple(tuple(pair) for pair in value["input_result_uids"]),
        )

    def affected_uids(self, issue_uid: str) -> tuple[str, ...]:
        issue = next(issue for issue in self.issues if issue.uid == issue_uid)
        instruction_uid = resolution_input_uid(self.decisions, issue_uid)
        # Provider source references, not text similarity, associate extra effects.
        additional = (
            effect.memory_uid
            for effect in self.effects
            if any(ref.memory_uid == instruction_uid for ref in effect.source_refs)
        )
        return tuple(dict.fromkeys((*issue.item_uids, *additional)))


def next_issue_analysis(proposal, *, direction_provider_factory) -> ResolveAnalysis:
    """Use the actual post-Audit and post-image, preserving the original scope."""
    audit = proposal.post_audit
    if audit is None:
        raise ValueError("An exact structural result has no next semantic Audit.")
    previous = proposal.analysis.frame
    known = {item.uid for item in previous.source.items}
    actionable = tuple(
        item.uid
        for item in audit.source.items
        if item.uid in previous.actionable_uids or item.uid not in known
    )
    frame = replace(
        previous,
        source=audit.source,
        revision=digest(
            {"previous": previous.revision, "audit": audit.snapshot_digest}
        ),
        actionable_uids=actionable,
    )
    analysis = analyze_resolve_audit(
        frame,
        audit,
        semantic_port=ProviderResolveOptionsPort(),
        direction_provider_factory=direction_provider_factory,
        rounds=proposal.rounds,
    )
    if not analysis.issues:
        raise ValueError(
            "The next Audit has no actionable response for its remaining issues."
        )
    return analysis
