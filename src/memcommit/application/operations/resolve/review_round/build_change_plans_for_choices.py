"""Freeze semantic choice effects before review and combine only selected plans."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace

from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.update.application import (
    apply_update_to_working_contexts,
)
from memcommit.application.operations.update.model import UpdatePlan, plan_update
from memcommit.application.operations.update.model.instruction import UpdateInstruction
from memcommit.models.context import Context
from ..model import ResolveError
from ..analysis.resolution_options.catalog import build_resolution_options
from ..analysis.resolution_options.kinds.duplicates import duplicate_choice_plan
from .finalize_review_decisions import ResolveDecision, ResolveDecisionSet
from memcommit.application.operations.resolve.review_round.build_update_input_from_decisions import (
    build_update_input_from_decisions,
    resolution_input_uid,
)
from .in_round_change_review.choose_change_for_memory import (
    ReviewedChoiceChanges,
    combine_reviewed_choice_effects,
)


@dataclass(frozen=True, slots=True)
class ResolveChoicePlan:
    revision: str
    decision: ResolveDecision
    _before: Context = field(repr=False)
    _after: Context = field(repr=False)
    _source: Context = field(repr=False)
    plan: UpdatePlan

    def __post_init__(self):
        for name in ("_before", "_after", "_source"):
            object.__setattr__(self, name, deepcopy(getattr(self, name)))

    def before(self):
        return deepcopy(self._before)

    def after(self):
        return deepcopy(self._after)

    def source(self):
        return deepcopy(self._source)


def prepare_resolve_choice(analysis, decision, *, provider_factory):
    """Generate one complete, detached choice; this never re-Audits or publishes."""
    issue = next(
        (item for item in analysis.issues if item.uid == decision.issue_uid), None
    )
    if (
        issue is None
        or decision.kind not in {"CONFIRM", "INTENT"}
        or decision.kind
        not in {choice.uid for choice in build_resolution_options(analysis, issue)}
    ):
        raise ResolveError("This issue has no such semantic choice.")
    before = analysis.frame.source.context()
    selected = ResolveDecisionSet(analysis.frame.revision, (decision,))
    source = build_update_input_from_decisions(analysis, selected)
    if issue.kind == "REDUNDANCY":
        plan = duplicate_choice_plan(analysis, selected, before)
    else:
        plan = plan_update(
            (source,),
            (before,),
            provider_factory,
            instruction=UpdateInstruction(next(iter(source.memories.values())).content),
        )
    result = apply_update_to_working_contexts(plan=plan, target_contexts=(before,))
    after = result.post_image_for(context_uid=before.uid)
    if after is None:
        after = before
    return ResolveChoicePlan(
        analysis.frame.revision, decision, before, after, source, plan
    )


def combine_choice_plans(target, plans):
    """Compatible overlaps share an effect; conflicting reviewed effects fail closed."""
    operations = {}
    for plan in plans:
        if plan.target_uid != target.uid or plan.target_name != target.name:
            raise ResolveError("A reviewed choice names a different Target.")
        for operation in plan.operations:
            key = (operation.owner_context_uid, operation.memory_uid)
            prior = operations.get(key)
            if prior is not None:
                if (
                    replace(
                        operation, source_refs=prior.source_refs, reason=prior.reason
                    )
                    != prior
                ):
                    raise ResolveError(
                        "The selected changes disagree about a Memory. Revise the choices."
                    )
                operation = replace(
                    prior,
                    source_refs=tuple(
                        dict.fromkeys((*prior.source_refs, *operation.source_refs))
                    ),
                )
            operations[key] = operation
    values = tuple(operations.values())
    return UpdatePlan(
        "resolve-choices-" + digest([item.to_dict() for item in values]),
        target.uid,
        target.name,
        values,
    )


def reviewed_choice_plans(analysis, decisions, choices, target):
    """Validate and bind each reviewed plan to its finalized decision identity."""
    source = build_update_input_from_decisions(analysis, decisions)
    plans = []
    for decision in decisions.decisions:
        issue = next(
            (item for item in analysis.issues if item.uid == decision.issue_uid)
        )
        if decision.kind not in {"CONFIRM", "INTENT"}:
            continue
        choice = choices.get(decision)
        if (
            choice is None
            or choice.revision != analysis.frame.revision
            or choice.decision != decision
        ):
            raise ResolveError(
                "The selected instruction has no reviewed change. Preview it first."
            )
        if choice.before().to_dict() != target.to_dict():
            raise ResolveError(
                "The reviewed change no longer matches this round's input."
            )
        result = apply_update_to_working_contexts(
            plan=choice.plan, target_contexts=(target,)
        )
        after = result.post_image_for(context_uid=target.uid)
        if after is None:
            after = target
        if after.to_dict() != choice.after().to_dict():
            raise ResolveError("The reviewed diff no longer matches its frozen plan.")
        if issue.kind == "REDUNDANCY":
            if choice.plan != duplicate_choice_plan(
                analysis,
                ResolveDecisionSet(analysis.frame.revision, (decision,)),
                target,
            ):
                raise ResolveError(
                    "The reviewed duplicate choice changed after preview."
                )
            plans.append((decision, choice.plan))
            continue
        old_source = choice.source()
        old_uid = next(iter(old_source.memories))
        new_uid = resolution_input_uid(decisions, decision.issue_uid)
        if old_source.memories[old_uid].content != source.memories[new_uid].content:
            raise ResolveError("The reviewed instruction changed after preview.")
        operations = tuple(
            (
                replace(
                    operation,
                    source_refs=tuple(
                        (
                            replace(
                                ref,
                                context_uid=source.uid,
                                context_name=source.name,
                                memory_uid=new_uid,
                            )
                            if ref.context_uid == old_source.uid
                            and ref.memory_uid == old_uid
                            else ref
                            for ref in operation.source_refs
                        )
                    ),
                )
                for operation in choice.plan.operations
            )
        )
        plans.append((decision, replace(choice.plan, operations=operations)))
    return tuple(plans)


def selected_choice_changes(
    analysis, decisions, choices, target, *, chosen_candidate_uids=None
) -> ReviewedChoiceChanges:
    """Combine exact reviewed plans after in-round Memory choices."""
    return combine_reviewed_choice_effects(
        target,
        reviewed_choice_plans(analysis, decisions, choices, target),
        chosen_candidate_uids,
    )


def selected_choice_plan(analysis, decisions, choices, target):
    """Preserve the existing plan-only caller for rounds without change conflicts."""
    return selected_choice_changes(analysis, decisions, choices, target).plan
