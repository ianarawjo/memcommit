"""Freeze semantic choice effects before review and combine only selected plans."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace

from memcommit.application.authorization import ContextUse
from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.update.application import (
    apply_update,
    materialize_update_post_image,
)
from memcommit.application.operations.update.model import UpdatePlan
from memcommit.application.operations.update.model.instruction import UpdateInstruction
from memcommit.core.context import Context
from memcommit.application.capabilities.context_memory_target import (
    plan_context_memory_update,
    ContextMemoryOrigin,
)
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


def allowed_target_uses(analysis):
    mapping = {
        "CREATE": ContextUse.CREATE,
        "UPDATE": ContextUse.UPDATE,
        "DELETE": ContextUse.DELETE,
    }
    return frozenset(mapping[value] for value in analysis.frame.allowed_effects)


@dataclass(frozen=True, slots=True)
class ResolveChoicePlan:
    revision: str
    decision: ResolveDecision
    _before: Context = field(repr=False)
    _after: Context = field(repr=False)
    _source: Context = field(repr=False)
    plan: UpdatePlan
    memory_origins: tuple[ContextMemoryOrigin, ...] = ()

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
        (item for item in analysis.issues if item.uid == decision.issue_uid),
        None,
    )
    if (
        issue is None
        or issue.item_kind != "MEMORY"
        or decision.kind not in {"CONFIRM", "INTENT"}
        or decision.kind
        not in {choice.uid for choice in build_resolution_options(analysis, issue)}
    ):
        raise ResolveError("This issue has no such semantic choice.")
    before = analysis.frame.source.context()
    selected = ResolveDecisionSet(analysis.frame.revision, (decision,))
    source = build_update_input_from_decisions(analysis, selected)
    memory_origins = ()
    if issue.kind == "REDUNDANCY":
        plan = duplicate_choice_plan(analysis, selected, before)
    else:
        plan, memory_origins = plan_context_memory_update(
            analysis.frame.memory_target,
            source,
            before,
            provider_factory,
            instruction=UpdateInstruction(next(iter(source.memories.values())).content),
            granted_target=analysis.frame.granted_binding,
            allowed_target_uses=allowed_target_uses(analysis),
        )
    after = materialize_update_post_image(apply_update(plan, before), before)
    return ResolveChoicePlan(
        analysis.frame.revision,
        decision,
        before,
        after,
        source,
        plan,
        memory_origins,
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
        issue = next(item for item in analysis.issues if item.uid == decision.issue_uid)
        if decision.kind not in {"CONFIRM", "INTENT"} or issue.item_kind != "MEMORY":
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
        if (
            materialize_update_post_image(
                apply_update(choice.plan, target), target
            ).to_dict()
            != choice.after().to_dict()
        ):
            raise ResolveError("The reviewed diff no longer matches its frozen plan.")
        if any(
            {"add": "CREATE", "edit": "UPDATE", "remove": "DELETE"}[operation.operation]
            not in analysis.frame.allowed_effects
            for operation in choice.plan.operations
        ):
            raise ResolveError("The reviewed change exceeds this frame's authority.")
        # The final decision set has a different instruction Context identity.
        # Rebind only the same authored instruction; effects and result IDs stay frozen.
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
            replace(
                operation,
                source_refs=tuple(
                    replace(
                        ref,
                        context_uid=source.uid,
                        context_name=source.name,
                        memory_uid=new_uid,
                    )
                    if ref.context_uid == old_source.uid and ref.memory_uid == old_uid
                    else ref
                    for ref in operation.source_refs
                ),
            )
            for operation in choice.plan.operations
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
