"""Record one review round's decisions, snapshots, and Memory effects."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from memcommit.core.context import Context
from memcommit.application.capabilities.resolution.workbench import ResolutionOption
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.update.model.changes import (
    UpdateOperation,
    _operation_from_dict,
)
from ..model import ResolveIssue
from .finalize_review_decisions import ResolveDecision, ResolveDecisionSet
from .build_update_input_from_decisions import resolution_input_uid
from .in_round_change_review.change_choice_record import ChangeChoiceRecord


@dataclass(frozen=True, slots=True)
class ReviewRoundRecord:
    """Review evidence shared by live Preview/lineage and decoded History."""

    audit: QualityAuditSession
    issues: tuple[ResolveIssue, ...]
    decisions: ResolveDecisionSet
    _before: Context = field(repr=False)
    _after: Context = field(repr=False)
    effects: tuple[UpdateOperation, ...] = ()
    input_result_uids: tuple[tuple[str, str], ...] | None = None
    change_choice_records: tuple[ChangeChoiceRecord, ...] = ()

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
            change_choice_records=[
                record.to_dict() for record in self.change_choice_records
            ],
        )

    @classmethod
    def from_dict(cls, value):
        """Decode persisted round evidence once, at the History read boundary."""
        required = {
            "audit",
            "issues",
            "decisions",
            "before",
            "after",
            "effects",
            "input_result_uids",
            "revision",
        }
        if (
            not isinstance(value, dict)
            or not required <= set(value)
            or set(value) - required - {"change_choice_records"}
        ):
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
            tuple(
                ChangeChoiceRecord.from_dict(record)
                for record in value.get("change_choice_records", ())
            ),
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
