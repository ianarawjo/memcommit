"""Application evidence for read-only Review of terminal checkpoints.

These records are application evidence, not resumable proposal sessions.  The
owning operation writes the evidence inside the same checkpoint as its Context
effect; Review later discovers that immutable terminal record without a
provider call or mutation. Console rendering belongs to the adapter layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from memcommit.persistence.store import MemoryStore
from memcommit.core.context_targeting.uid_locator import resolve_exact_or_unique_uid


CHECKPOINT_REVIEW_OPERATIONS = frozenset(
    {"dedun", "distill", "makemore", "forget", "resolve"}
)

# Makemore is the new public name for the former Elaborate operation.  Keep the
# persisted command and nested payload key readable without re-exposing the old
# name as a callable Review operation.
_CHECKPOINT_COMMANDS_BY_REVIEW_OPERATION = {
    "makemore": frozenset({"makemore", "elaborate"}),
}


def _matches_review_operation(
    operation: str,
    stored_operation: str,
    checkpoint: dict,
) -> bool:
    """Keep legacy Makemore evidence distinct from append-only Elaborate."""

    args = checkpoint.get("args")
    append_only = (
        isinstance(args, dict)
        and args.get("contract") == "append-only-v1"
    )
    if operation == "makemore" and stored_operation == "elaborate":
        return not append_only
    accepted = _CHECKPOINT_COMMANDS_BY_REVIEW_OPERATION.get(
        operation,
        frozenset({operation}),
    )
    return stored_operation in accepted


@dataclass(frozen=True)
class AppliedCheckpointReview:
    """One immutable terminal checkpoint and its operation-owned evidence."""

    operation: str
    checkpoint_uid: str
    context_name: str
    timestamp: str
    description: str
    payload: dict[str, object]

    @property
    def revision(self) -> str:
        encoded = json.dumps(
            {
                "operation": self.operation,
                "checkpoint_uid": self.checkpoint_uid,
                "context_name": self.context_name,
                "timestamp": self.timestamp,
                "description": self.description,
                "payload": self.payload,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _checkpoint_payload(stored_operation: str, checkpoint: dict) -> dict[str, object]:
    args = checkpoint.get("args")
    if not isinstance(args, dict):
        return {}
    nested = args.get(stored_operation)
    return dict(nested) if isinstance(nested, dict) else dict(args)


def list_applied_checkpoint_reviews(
    store: MemoryStore,
    operation: str,
) -> tuple[AppliedCheckpointReview, ...]:
    """List local terminal evidence newest-first without opening providers."""

    normalized = operation.casefold()
    if normalized not in CHECKPOINT_REVIEW_OPERATIONS:
        raise ValueError(f"Unsupported checkpoint Review operation '{operation}'.")
    records: list[AppliedCheckpointReview] = []
    for context_name in store.list_context_names():
        for checkpoint in store.list_checkpoints(context_name):
            stored_operation = str(checkpoint.get("command", "")).casefold()
            if not _matches_review_operation(
                normalized,
                stored_operation,
                checkpoint,
            ):
                continue
            uid = checkpoint.get("uid")
            timestamp = checkpoint.get("timestamp")
            if not isinstance(uid, str) or not isinstance(timestamp, str):
                raise ValueError(
                    f"Stored {operation.title()} checkpoint evidence is invalid."
                )
            description = checkpoint.get("description")
            records.append(
                AppliedCheckpointReview(
                    operation=normalized,
                    checkpoint_uid=uid,
                    context_name=context_name,
                    timestamp=timestamp,
                    description=description if isinstance(description, str) else "",
                    payload=_checkpoint_payload(stored_operation, checkpoint),
                )
            )
    return tuple(sorted(records, key=lambda item: item.timestamp, reverse=True))


def select_applied_checkpoint_review(
    records: Iterable[AppliedCheckpointReview],
    selector: str,
) -> AppliedCheckpointReview:
    """Resolve one exact or unambiguous receipt prefix."""

    return resolve_exact_or_unique_uid(
        records,
        selector,
        uid=lambda record: record.checkpoint_uid,
        label="Review receipt",
    )


__all__ = [
    "AppliedCheckpointReview",
    "CHECKPOINT_REVIEW_OPERATIONS",
    "list_applied_checkpoint_reviews",
    "select_applied_checkpoint_review",
]
