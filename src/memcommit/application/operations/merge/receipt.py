"""Frozen completion counts shared by Literal and Semantic Merge receipts."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class MergeReceiptSummary:
    method: Literal["LITERAL", "SEMANTIC + LITERAL"]
    sources: tuple[tuple[str, int], ...]
    targets: tuple[tuple[str, int, int], ...]
    decisions_applied: int
    issues_left_unresolved: int

    def __post_init__(self):
        if (
            self.method not in {"LITERAL", "SEMANTIC + LITERAL"}
            or not self.sources
            or not self.targets
        ):
            raise ValueError(
                "Merge receipt requires its method and complete endpoints."
            )
        counts = (
            self.decisions_applied,
            self.issues_left_unresolved,
            *(count for _name, count in self.sources),
            *(
                count
                for _name, before, after in self.targets
                for count in (before, after)
            ),
        )
        if any(type(count) is not int or count < 0 for count in counts):
            raise ValueError("Merge receipt counts must be nonnegative integers.")


@dataclass(frozen=True, slots=True)
class MergeReceipt:
    """One durable publication identity and its shared user-facing counts."""

    operation_uid: str
    target_uid: str
    checkpoint_uid: str
    summary: MergeReceiptSummary

    def __post_init__(self):
        if not all(
            isinstance(value, str) and value
            for value in (self.operation_uid, self.target_uid, self.checkpoint_uid)
        ) or not isinstance(self.summary, MergeReceiptSummary):
            raise ValueError("Merge receipt requires its exact publication identity.")


def merge_receipt_summary(prepared, result) -> MergeReceiptSummary:
    from memcommit.core.context import Memory

    def count(context):
        return sum(isinstance(item, Memory) for item in context.iter_items())

    return MergeReceiptSummary(
        "LITERAL" if prepared.request.method == "LITERAL" else "SEMANTIC + LITERAL",
        ((prepared.request.source, count(prepared.inputs.source())),),
        (
            (
                prepared.request.target,
                count(prepared.inputs.target()),
                count(result.post_image),
            ),
        ),
        sum(
            decision.kind != "FORCE"
            for round in result.rounds
            for decision in round.decisions.decisions
        ),
        len(result.unresolved_issue_uids),
    )
