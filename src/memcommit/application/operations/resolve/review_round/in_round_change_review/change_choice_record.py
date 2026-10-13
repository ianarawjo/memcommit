"""Keep the exact candidate and winning change for one in-round review."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from memcommit.application.operations.update.model.changes import _operation_from_dict

from ..finalize_review_decisions import ResolveDecision
from .find_conflicting_changes import ProposedMemoryChange


@dataclass(frozen=True, slots=True)
class ChangeChoiceRecord:
    owner_context_uid: str
    memory_uid: str
    candidates: tuple[ProposedMemoryChange, ...]
    chosen_candidate_uid: str
    selection_kind: Literal["INTENT_PRIORITY", "USER_CHOICE"]

    def to_dict(self) -> dict[str, object]:
        return {
            "owner_context_uid": self.owner_context_uid,
            "memory_uid": self.memory_uid,
            "candidates": [
                {
                    "uid": item.uid,
                    "decision": asdict(item.decision),
                    "operation": item.operation.to_dict(),
                }
                for item in self.candidates
            ],
            "chosen_candidate_uid": self.chosen_candidate_uid,
            "selection_kind": self.selection_kind,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> ChangeChoiceRecord:
        if not isinstance(value, dict) or set(value) != {
            "owner_context_uid",
            "memory_uid",
            "candidates",
            "chosen_candidate_uid",
            "selection_kind",
        }:
            raise ValueError("Invalid in-round change choice record.")
        candidates = tuple(
            ProposedMemoryChange(
                item["uid"],
                ResolveDecision(**item["decision"]),
                _operation_from_dict(item["operation"]),
            )
            for item in value["candidates"]
        )
        result = cls(
            value["owner_context_uid"],
            value["memory_uid"],
            candidates,
            value["chosen_candidate_uid"],
            value["selection_kind"],
        )
        if (
            result.selection_kind not in {"INTENT_PRIORITY", "USER_CHOICE"}
            or result.chosen_candidate_uid not in {item.uid for item in candidates}
            or any(
                item.uid
                != ProposedMemoryChange.from_choice(item.decision, item.operation).uid
                for item in candidates
            )
        ):
            raise ValueError("Invalid in-round change choice record.")
        return result
