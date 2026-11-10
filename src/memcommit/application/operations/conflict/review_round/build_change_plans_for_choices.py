"""Freeze semantic choice effects before review and combine only selected plans."""

from __future__ import annotations

from memcommit.application.operations.update.model.inputs import collect_update_inputs

from copy import deepcopy
from dataclasses import dataclass, field, replace

from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.update.application import (
    apply_update_to_working_contexts,
)
from memcommit.application.operations.update.model import UpdatePlan, plan_update
from memcommit.models.context import Context
from ..model import ConflictResolutionError
from ..analysis.resolution_options.conflicts import build_resolution_options
from .finalize_review_decisions import (
    ConflictResolutionDecision,
    ConflictResolutionDecisionSet,
)
from memcommit.application.operations.conflict.review_round.build_update_input_from_decisions import (
    build_update_input_from_decisions,
    resolution_input_uid,
)
from .in_round_change_review.choose_change_for_memory import (
    ReviewedChoiceChanges,
    combine_reviewed_choice_effects,
)


@dataclass(frozen=True, slots=True)
class ConflictResolutionChoicePlan:
    revision: str
    decision: ConflictResolutionDecision
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


def prepare_conflict_resolution_choice(analysis, decision, *, provider_factory):
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
        raise ConflictResolutionError("This issue has no such semantic choice.")
    before = analysis.frame.source.context()
    selected = ConflictResolutionDecisionSet(analysis.frame.revision, (decision,))
    source = build_update_input_from_decisions(analysis, selected)
    plan = plan_update(
        collect_update_inputs(
            (source,),
            (before,),
            instruction=next(iter(source.memories.values())).content,
        ),
        provider_factory,
    )
    result = apply_update_to_working_contexts(plan=plan, target_contexts=(before,))
    after = result.get_updated_context(context_uid=before.uid)
    if after is None:
        after = before
    return ConflictResolutionChoicePlan(
        analysis.frame.revision, decision, before, after, source, plan
    )


def combine_choice_plans(target, plans):
    """Compatible overlaps share an effect; conflicting reviewed effects fail closed."""
    operations = {}
    for plan in plans:
        if plan.target_uid != target.uid or plan.target_name != target.name:
            raise ConflictResolutionError("A reviewed choice names a different Target.")
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
                    raise ConflictResolutionError(
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
        "conflict-resolution-choices-" + digest([item.to_dict() for item in values]),
        target.uid,
        target.name,
        values,
    )


def reviewed_choice_plans(analysis, decisions, choices, target):
    """Validate and bind each reviewed plan to its finalized decision identity."""
    source = build_update_input_from_decisions(analysis, decisions)
    plans = []
    for decision in decisions.decisions:
        if decision.kind not in {"CONFIRM", "INTENT"}:
            continue
        choice = choices.get(decision)
        if (
            choice is None
            or choice.revision != analysis.frame.revision
            or choice.decision != decision
        ):
            raise ConflictResolutionError(
                "The selected instruction has no reviewed change. Preview it first."
            )
        if choice.before().to_dict() != target.to_dict():
            raise ConflictResolutionError(
                "The reviewed change no longer matches this round's input."
            )
        result = apply_update_to_working_contexts(
            plan=choice.plan, target_contexts=(target,)
        )
        after = result.get_updated_context(context_uid=target.uid)
        if after is None:
            after = target
        if after.to_dict() != choice.after().to_dict():
            raise ConflictResolutionError(
                "The reviewed diff no longer matches its frozen plan."
            )
        old_source = choice.source()
        old_uid = next(iter(old_source.memories))
        new_uid = resolution_input_uid(decisions, decision.issue_uid)
        if old_source.memories[old_uid].content != source.memories[new_uid].content:
            raise ConflictResolutionError(
                "The reviewed instruction changed after preview."
            )
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
