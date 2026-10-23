"""Choose one exact change for each Memory, then build one Update plan."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.update.model import UpdatePlan
from memcommit.application.operations.update.model.changes import UpdateOperation
from memcommit.models.context import Context

from ..finalize_review_decisions import ResolveDecision
from ...model import ResolveError
from .change_choice_record import ChangeChoiceRecord
from .find_conflicting_changes import (
    change_effect,
    collect_proposed_memory_changes,
    find_conflicting_changes,
)


@dataclass(frozen=True, slots=True)
class ReviewedChoiceChanges:
    plan: UpdatePlan
    change_choice_records: tuple[ChangeChoiceRecord, ...]


def choose_change_for_memory(
    conflict, chosen_candidate_uid: str | None
) -> tuple[UpdateOperation, ChangeChoiceRecord]:
    """Honor an explicit review or the single distinct user Intent outcome."""
    by_uid = {candidate.uid: candidate for candidate in conflict.candidates}
    if chosen_candidate_uid is not None:
        if chosen_candidate_uid not in by_uid:
            raise ResolveError("The reviewed change choice is unavailable.")
        selection_kind = "USER_CHOICE"
    else:
        chosen_candidate_uid = conflict.priority_intent_candidate_uid
        if chosen_candidate_uid is None:
            raise ResolveError("Choose one change for each overlapping Memory.")
        selection_kind = "INTENT_PRIORITY"
    candidate = by_uid[chosen_candidate_uid]
    return candidate.operation, ChangeChoiceRecord(
        conflict.owner_context_uid,
        conflict.memory_uid,
        conflict.candidates,
        chosen_candidate_uid,
        selection_kind,
    )


def combine_reviewed_choice_effects(
    target: Context,
    reviewed_choice_plans: tuple[tuple[ResolveDecision, UpdatePlan], ...],
    chosen_candidate_uids: Mapping[tuple[str, str], str] | None = None,
) -> ReviewedChoiceChanges:
    """Share equal effects and apply exactly one reviewed effect per Memory."""
    choices = chosen_candidate_uids or {}
    for _, plan in reviewed_choice_plans:
        if plan.target_uid != target.uid or plan.target_name != target.name:
            raise ResolveError("A reviewed choice names a different Target.")
    conflicts = {
        item.memory_key: item
        for item in find_conflicting_changes(reviewed_choice_plans)
    }
    proposed = collect_proposed_memory_changes(reviewed_choice_plans)
    if set(choices) - set(conflicts):
        raise ResolveError("A reviewed change choice no longer has a conflict.")
    operations = []
    records = []
    for key, candidates in proposed.items():
        conflict = conflicts.get(key)
        if conflict is not None:
            operation, record = choose_change_for_memory(conflict, choices.get(key))
            operations.append(operation)
            records.append(record)
            continue
        first = candidates[0].operation
        refs = tuple(
            dict.fromkeys(
                ref
                for candidate in candidates
                for ref in candidate.operation.source_refs
            )
        )
        if any(
            change_effect(item.operation) != change_effect(first) for item in candidates
        ):
            raise ResolveError("Equal choice changes could not be combined.")
        operations.append(replace(first, source_refs=refs))
    plan = UpdatePlan(
        "resolve-choices-" + digest([item.to_dict() for item in operations]),
        target.uid,
        target.name,
        tuple(operations),
    )
    return ReviewedChoiceChanges(plan, tuple(records))
