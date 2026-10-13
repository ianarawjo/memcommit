"""Find Memories changed differently by choices in the same Resolve round."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.update.model import UpdatePlan
from memcommit.application.operations.update.model.changes import UpdateOperation

from ..finalize_review_decisions import ResolveDecision


def change_effect(operation: UpdateOperation) -> dict[str, object]:
    """Compare exact changes without treating explanations as changed content."""
    return {
        key: value
        for key, value in operation.to_dict().items()
        if key not in {"source_refs", "reason"}
    }


@dataclass(frozen=True, slots=True)
class ProposedMemoryChange:
    uid: str
    decision: ResolveDecision
    operation: UpdateOperation

    @classmethod
    def from_choice(
        cls, decision: ResolveDecision, operation: UpdateOperation
    ) -> ProposedMemoryChange:
        return cls(
            digest({"decision": asdict(decision), "effect": change_effect(operation)}),
            decision,
            operation,
        )


@dataclass(frozen=True, slots=True)
class ConflictingMemoryChanges:
    owner_context_uid: str
    owner_context_name: str
    memory_uid: str
    candidates: tuple[ProposedMemoryChange, ...]

    @property
    def memory_key(self) -> tuple[str, str]:
        return self.owner_context_uid, self.memory_uid

    @property
    def priority_intent_candidate_uid(self) -> str | None:
        intent_candidates = tuple(
            candidate
            for candidate in self.candidates
            if candidate.decision.kind == "INTENT"
        )
        if (
            len({digest(change_effect(item.operation)) for item in intent_candidates})
            == 1
        ):
            return intent_candidates[0].uid
        return None


def collect_proposed_memory_changes(
    reviewed_choice_plans: tuple[tuple[ResolveDecision, UpdatePlan], ...],
) -> dict[tuple[str, str], tuple[ProposedMemoryChange, ...]]:
    """Retain every choice, including equal outcomes with different provenance."""
    changes: dict[tuple[str, str], list[ProposedMemoryChange]] = {}
    for decision, plan in reviewed_choice_plans:
        for operation in plan.operations:
            key = operation.owner_context_uid, operation.memory_uid
            changes.setdefault(key, []).append(
                ProposedMemoryChange.from_choice(decision, operation)
            )
    return {key: tuple(candidates) for key, candidates in changes.items()}


def find_conflicting_changes(
    reviewed_choice_plans: tuple[tuple[ResolveDecision, UpdatePlan], ...],
) -> tuple[ConflictingMemoryChanges, ...]:
    """Return all choices for every Memory with distinct proposed outcomes."""
    groups = []
    for (owner_uid, memory_uid), candidates in collect_proposed_memory_changes(
        reviewed_choice_plans
    ).items():
        if len({digest(change_effect(item.operation)) for item in candidates}) < 2:
            continue
        groups.append(
            ConflictingMemoryChanges(
                owner_uid,
                candidates[0].operation.owner_context_name,
                memory_uid,
                candidates,
            )
        )
    return tuple(groups)
