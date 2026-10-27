"""Prepare and verify detached Resolve results; callers own final publication."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsProvider,
)
from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.audit.application import audit_post_image
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.update.application import (
    apply_update_to_working_contexts,
)
from memcommit.application.operations.update.model import (
    UpdatePlan,
    plan_update,
    UpdateProvider,
    UpdateResult,
)
from memcommit.models.context import Context
from ..application import ResolveApplyPort
from ..model import ResolveAnalysis, ResolveError, ResolveReceipt
from ..review_round.build_change_plans_for_choices import (
    combine_choice_plans,
    selected_choice_changes,
)
from ..analysis.resolution_options.kinds.duplicates import duplicate_choice_plan
from ..review_round.finalize_review_decisions import (
    KEEP_DECISIONS,
    ResolveDecision,
    ResolveDecisionSet,
    ResolveFinalizedInput,
    finalize_resolve_decisions,
)
from memcommit.application.operations.resolve.review_round.build_update_input_from_decisions import (
    _source_identity,
    build_update_input_from_decisions,
)
from memcommit.application.operations.resolve.review_round.review_round_record import (
    ReviewRoundRecord,
)
from memcommit.application.operations.resolve.review_round.review_session import (
    ResolveReviewSession,
)
from .materialization import compose_plan
from ..analysis.select_issues_for_review import (
    forced_review_issues,
    remaining_review_issues,
)


@dataclass(frozen=True, slots=True)
class ResolveProposal:
    """Detached cumulative result and evidence of finalized review rounds."""

    analysis: ResolveAnalysis
    decisions: ResolveDecisionSet
    source: Context | None
    target: Context
    plan: UpdatePlan | None
    result: UpdateResult | None
    post_image: Context
    post_audit: QualityAuditSession | None
    blocking_audit_keys: tuple[str, ...]
    rounds: tuple[ReviewRoundRecord, ...] = ()
    initial_analysis: ResolveAnalysis | None = None
    review_input: ResolveReviewSession | None = field(
        default=None, repr=False, compare=False
    )

    @property
    def digest(self) -> str:
        return digest(
            {
                "revision": self.analysis.frame.revision,
                "audit": self.analysis.audit.snapshot_digest,
                "decisions": asdict(self.decisions),
                "target": self.target.to_dict(),
                "source": self.source.to_dict() if self.source is not None else None,
                "plan": self.plan.digest if self.plan is not None else None,
                "post_image": self.post_image.to_dict(),
                "post_audit": self.post_audit.to_dict()
                if self.post_audit is not None
                else None,
                "blocking": self.blocking_audit_keys,
                "rounds": [round.to_dict() for round in self.rounds],
                "initial_revision": self.initial_analysis.frame.revision
                if self.initial_analysis
                else None,
            }
        )

    @property
    def forced_audit_keys(self) -> tuple[str, ...]:
        if self.post_audit is None:
            return ()
        return tuple(
            (key for key, _ in forced_review_issues(self.post_audit, self.rounds))
        )

    @property
    def unresolved_issue_uids(self) -> tuple[str, ...]:
        if self.post_audit is None:
            return ()
        return tuple(
            (uid for _, uid in forced_review_issues(self.post_audit, self.rounds))
        )

    @property
    def ready_to_apply(self) -> bool:
        return not self.blocking_audit_keys

    @property
    def finalized_inputs(self) -> tuple[ResolveFinalizedInput, ...]:
        inputs = []
        for round in self.rounds:
            issues = {issue.uid: issue for issue in round.issues}
            for decision in round.decisions.decisions:
                inputs.append(
                    ResolveFinalizedInput(
                        issue_uid=decision.issue_uid,
                        kind=decision.kind,
                        content=issues[decision.issue_uid].proposed_direction
                        if decision.kind == "CONFIRM"
                        else decision.intent
                        if decision.kind == "INTENT"
                        else "",
                    )
                )
        return tuple(inputs)


def prepare_resolve_proposal(
    analysis: ResolveAnalysis,
    decisions: tuple[ResolveDecision, ...],
    *,
    update_provider_factory: Callable[[], UpdateProvider],
    audit_provider_factory: Callable[[], FindingsProvider],
    previous: ResolveProposal | None = None,
    reviewed_choices=None,
    chosen_candidate_uids=None,
) -> ResolveProposal:
    """Apply exact choices or accepted semantic instructions, then verify the result."""
    finalized = finalize_resolve_decisions(analysis, decisions)
    if analysis.audit is None:
        raise ResolveError("Resolve Update planning requires its exact Audit.")
    working_target = analysis.frame.source.context()
    if (
        previous is not None
        and working_target.to_dict() != previous.post_image.to_dict()
    ):
        raise ResolveError("The next review is not bound to the previous result.")
    target = previous.target if previous is not None else working_target
    preserved = {
        uid: working_target.memories[uid].to_dict()
        for decision in finalized.decisions
        if decision.kind in KEEP_DECISIONS
        for issue in analysis.issues
        if issue.uid == decision.issue_uid
        for uid in issue.item_uids
    }
    preserved.update(
        {
            issue.item_uids[0]: working_target.memories[issue.item_uids[0]].to_dict()
            for decision in finalized.decisions
            if decision.kind == "CONFIRM"
            for issue in analysis.issues
            if issue.uid == decision.issue_uid and issue.kind == "REDUNDANCY"
        }
    )
    source = build_update_input_from_decisions(analysis, finalized)
    {issue.uid: issue for issue in analysis.issues}
    change_choice_records = ()
    if reviewed_choices is not None:
        reviewed_changes = selected_choice_changes(
            analysis,
            finalized,
            reviewed_choices,
            working_target,
            chosen_candidate_uids=chosen_candidate_uids,
        )
        plan = reviewed_changes.plan
        change_choice_records = reviewed_changes.change_choice_records
    elif source.memories:
        plan = plan_update(
            (source,),
            (working_target,),
            update_provider_factory,
        )
    else:
        plan = UpdatePlan(
            uid=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"memcommit:resolve-force:{_source_identity(finalized)}",
                )
            ),
            target_uid=target.uid,
            target_name=target.name,
            operations=(),
        )
    duplicate_plan = duplicate_choice_plan(analysis, finalized, working_target)
    semantic_plan = (
        combine_choice_plans(working_target, (plan, duplicate_plan))
        if duplicate_plan.operations
        else plan
    )
    stage_result = apply_update_to_working_contexts(
        plan=semantic_plan, target_contexts=(working_target,)
    )
    after = stage_result.post_image_for(context_uid=working_target.uid)
    if after is None:
        after = working_target
    if any(
        (
            uid not in after.memories or after.memories[uid].to_dict() != value
            for uid, value in preserved.items()
        )
    ):
        raise ResolveError("Generated changes contradict a preservation choice.")
    plan = compose_plan(
        target, after, ((previous.plan,) if previous else ()) + (semantic_plan,)
    )
    result = apply_update_to_working_contexts(plan=plan, target_contexts=(target,))
    updated_context = result.post_image_for(context_uid=target.uid)
    post_image = deepcopy(target if updated_context is None else updated_context)
    post_audit = audit_post_image(analysis.audit, post_image, audit_provider_factory)
    round_plan = compose_plan(working_target, post_image, (semantic_plan,))
    round = ReviewRoundRecord(
        analysis.audit,
        analysis.issues,
        finalized,
        working_target,
        post_image,
        round_plan.operations,
        change_choice_records=change_choice_records,
    )
    rounds = (previous.rounds if previous else ()) + (round,)
    blocking = tuple(
        (
            issue.audit_key
            for issue in remaining_review_issues(post_audit, rounds=rounds)
        )
    )
    return ResolveProposal(
        analysis=analysis,
        decisions=finalized,
        source=source,
        target=target,
        plan=plan,
        result=result,
        post_image=post_image,
        post_audit=post_audit,
        blocking_audit_keys=blocking,
        rounds=rounds,
        initial_analysis=previous.initial_analysis or previous.analysis
        if previous
        else analysis,
    )


def apply_resolve_proposal(
    proposal: ResolveProposal, *, apply_port: ResolveApplyPort
) -> ResolveReceipt:
    """Publish the exact reviewed Update plan through Resolve authority."""
    if not isinstance(proposal, ResolveProposal):
        raise TypeError("Resolve Apply requires a typed Update proposal.")
    if proposal.blocking_audit_keys:
        raise ResolveError(
            "The proposed whole Context still contains an unforced Audit issue; Resolve must collect another decision before Apply."
        )
    if proposal.plan is None:
        raise ResolveError(
            "The composing operation owns structural result publication."
        )
    return apply_port.apply_update_plan(
        (proposal.initial_analysis or proposal.analysis).frame,
        proposal.plan,
        unresolved_issue_uids=proposal.unresolved_issue_uids,
        finalized_inputs=proposal.finalized_inputs,
    )


__all__ = ["ResolveProposal", "prepare_resolve_proposal", "apply_resolve_proposal"]
