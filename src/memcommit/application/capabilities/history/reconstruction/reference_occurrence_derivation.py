"""Derive typed History for one direct Memory reference occurrence.

A MemoryRef has its own durable identity in the parent Context and points to a
separate Memory identity in a Source Context.  This module keeps those two
histories separate: occurrence events explain why the pointer is present,
while a downstream projection may independently explain the referenced target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.core.context import Context, GrantedMemorySource, MemoryRef
from memcommit.application.capabilities.history.verification import (
    MemoryHistoryReconstructionError,
)
from memcommit.application.capabilities.history.history_evidence_source import (
    HistoryEvidenceSource,
)


ReferenceMode = Literal["LIVE", "SNAPSHOT"]
ReferenceEventKind = Literal[
    "CREATED",
    "REMOVED",
    "RESTORED",
    "RETARGETED",
    "TARGET_RENAMED",
    "REORDERED",
    "EARLIEST_RETAINED",
    "HISTORY_GAP",
]
ReferenceEvidence = Literal["RECORDED", "RECONSTRUCTED", "UNRECORDED"]


@dataclass(frozen=True)
class MemoryReferenceState:
    """One exact serialized state of a direct MemoryRef occurrence."""

    uid: str
    mode: ReferenceMode
    target_context_uid: str
    target_context_name: str
    target_memory_uid: str
    position: int
    snapshot_content: str | None = None
    snapshot_content_sha256: str | None = None
    grant_source: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "mode": self.mode,
            "target_context": {
                "uid": self.target_context_uid,
                "name": self.target_context_name,
            },
            "target_memory_uid": self.target_memory_uid,
            "position": self.position,
            "snapshot_content": self.snapshot_content,
            "snapshot_content_sha256": self.snapshot_content_sha256,
            "grant_source": self.grant_source,
        }


@dataclass(frozen=True)
class MemoryReferenceCandidate:
    """One current or retained-only MemoryRef selector candidate."""

    state: MemoryReferenceState
    status: Literal["CURRENT", "HISTORICAL"]
    change_count: int


@dataclass(frozen=True)
class MemoryReferenceHistoryEvent:
    """One retained command boundary that changed a reference occurrence."""

    kind: ReferenceEventKind
    evidence: ReferenceEvidence
    timestamp: str | None
    checkpoint_uid: str | None
    command: str
    description: str
    before: MemoryReferenceState | None
    after: MemoryReferenceState | None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "checkpoint_uid": self.checkpoint_uid,
            "command": self.command,
            "description": self.description,
            "before": self.before.to_dict() if self.before is not None else None,
            "after": self.after.to_dict() if self.after is not None else None,
        }


def _ordered_item_uids(snapshot: dict[str, object]) -> tuple[str, ...]:
    serialized = snapshot.get("memories")
    if not isinstance(serialized, dict):
        return ()
    requested = snapshot.get("order")
    ordered: list[str] = []
    seen: set[str] = set()
    if isinstance(requested, list):
        for uid in requested:
            if isinstance(uid, str) and uid in serialized and uid not in seen:
                ordered.append(uid)
                seen.add(uid)
    for uid in serialized:
        if isinstance(uid, str) and uid not in seen:
            ordered.append(uid)
            seen.add(uid)
    return tuple(ordered)


def _state_from_snapshot(
    snapshot: object,
    uid: str,
) -> MemoryReferenceState | None:
    if not isinstance(snapshot, dict):
        return None
    serialized = snapshot.get("memories")
    if not isinstance(serialized, dict):
        return None
    item = serialized.get(uid)
    if not isinstance(item, dict):
        return None
    item_type = item.get("type")
    if item_type not in {
        "memory_ref",
        "memory_snapshot_ref",
        "granted_memory_ref",
    }:
        return None
    item_uid = item.get("uid")
    target_context = item.get("target_context")
    target_memory_uid = item.get("target_memory_uid")
    if (
        item_uid != uid
        or not isinstance(target_context, dict)
        or not isinstance(target_context.get("uid"), str)
        or not isinstance(target_context.get("name"), str)
        or not isinstance(target_memory_uid, str)
    ):
        raise MemoryHistoryReconstructionError("Retained Memory reference identity is invalid.")
    order = _ordered_item_uids(snapshot)
    position = order.index(uid) if uid in order else len(order)
    content = item.get("content") if item_type == "memory_snapshot_ref" else None
    digest = item.get("content_sha256") if item_type == "memory_snapshot_ref" else None
    if item_type == "memory_snapshot_ref" and (
        not isinstance(content, str) or not isinstance(digest, str)
    ):
        raise MemoryHistoryReconstructionError("Retained Memory snapshot reference is invalid.")
    raw_grant_source = item.get("grant_source")
    grant_source = None
    if raw_grant_source is not None:
        if not isinstance(raw_grant_source, dict):
            raise MemoryHistoryReconstructionError("Retained Grant provenance is invalid.")
        try:
            grant_source = GrantedMemorySource.from_dict(raw_grant_source).to_dict()
        except (KeyError, TypeError, ValueError) as error:
            raise MemoryHistoryReconstructionError("Retained Grant provenance is invalid.") from error
    if item_type == "granted_memory_ref" and grant_source is None:
        raise MemoryHistoryReconstructionError("Granted Memory Embed provenance is missing.")
    return MemoryReferenceState(
        uid=uid,
        mode="SNAPSHOT" if item_type == "memory_snapshot_ref" else "LIVE",
        target_context_uid=target_context["uid"],
        target_context_name=target_context["name"],
        target_memory_uid=target_memory_uid,
        position=position,
        snapshot_content=content,
        snapshot_content_sha256=digest,
        grant_source=grant_source,
    )


def _reference_uids(snapshot: object) -> tuple[str, ...]:
    if not isinstance(snapshot, dict):
        return ()
    serialized = snapshot.get("memories")
    if not isinstance(serialized, dict):
        return ()
    return tuple(
        uid
        for uid, item in serialized.items()
        if isinstance(uid, str)
        and isinstance(item, dict)
        and item.get("type")
        in {"memory_ref", "memory_snapshot_ref", "granted_memory_ref"}
    )


def _event_kind(
    before: MemoryReferenceState | None,
    after: MemoryReferenceState | None,
    *,
    command: str,
    first_observation: bool,
) -> ReferenceEventKind:
    if first_observation:
        return "EARLIEST_RETAINED"
    if before is None and after is not None:
        return "RESTORED" if command in {"undo", "redo", "revert"} else "CREATED"
    if before is not None and after is None:
        return "REMOVED"
    assert before is not None and after is not None
    before_target = (
        before.mode,
        before.target_context_uid,
        before.target_memory_uid,
        before.snapshot_content_sha256,
        before.grant_source,
    )
    after_target = (
        after.mode,
        after.target_context_uid,
        after.target_memory_uid,
        after.snapshot_content_sha256,
        after.grant_source,
    )
    if before_target != after_target:
        return "RETARGETED"
    if before.target_context_name != after.target_context_name:
        return "TARGET_RENAMED"
    return "REORDERED"


def reference_occurrence_events(
    store: HistoryEvidenceSource,
    context: Context,
    uid: str,
) -> tuple[tuple[MemoryReferenceHistoryEvent, ...], MemoryReferenceState | None]:
    checkpoints = tuple(reversed(store.list_checkpoints(context.name)))
    events: list[MemoryReferenceHistoryEvent] = []
    previous: MemoryReferenceState | None = None
    previous_known = False
    for checkpoint in checkpoints:
        snapshot = checkpoint.get("snapshot")
        after = _state_from_snapshot(snapshot, uid)
        command_before = checkpoint.get("command_before")
        if isinstance(command_before, dict):
            before = _state_from_snapshot(command_before, uid)
            known_before = True
        else:
            before = previous
            known_before = previous_known
        if before == after:
            previous = after
            previous_known = True
            continue
        command = checkpoint.get("command")
        timestamp = checkpoint.get("timestamp")
        checkpoint_uid = checkpoint.get("uid")
        description = checkpoint.get("description")
        events.append(
            MemoryReferenceHistoryEvent(
                kind=_event_kind(
                    before,
                    after,
                    command=command if isinstance(command, str) else "checkpoint",
                    first_observation=not known_before and after is not None,
                ),
                evidence="RECORDED" if known_before else "RECONSTRUCTED",
                timestamp=timestamp if isinstance(timestamp, str) else None,
                checkpoint_uid=(
                    checkpoint_uid if isinstance(checkpoint_uid, str) else None
                ),
                command=command if isinstance(command, str) else "checkpoint",
                description=description if isinstance(description, str) else "",
                before=before,
                after=after,
            )
        )
        previous = after
        previous_known = True

    current = _state_from_snapshot(context.to_dict(), uid)
    if previous_known and current != previous:
        events.append(
            MemoryReferenceHistoryEvent(
                kind="HISTORY_GAP",
                evidence="UNRECORDED",
                timestamp=None,
                checkpoint_uid=None,
                command="current",
                description=(
                    "Current reference state differs from the last retained checkpoint."
                ),
                before=previous,
                after=current,
            )
        )
    return tuple(events), current


def collect_reference_candidates(
    store: HistoryEvidenceSource,
    context: Context,
) -> tuple[MemoryReferenceCandidate, ...]:
    """Return current then retained-only reference identities for one owner."""

    known: list[str] = []
    for item in context.iter_items():
        if isinstance(item, MemoryRef):
            known.append(item.uid)
    for checkpoint in reversed(store.list_checkpoints(context.name)):
        for uid in _reference_uids(checkpoint.get("snapshot")):
            if uid not in known:
                known.append(uid)
        for uid in _reference_uids(checkpoint.get("command_before")):
            if uid not in known:
                known.append(uid)

    candidates: list[MemoryReferenceCandidate] = []
    current_record = context.to_dict()
    for uid in known:
        events, current = reference_occurrence_events(store, context, uid)
        state = current
        if state is None:
            for event in reversed(events):
                state = event.after or event.before
                if state is not None:
                    break
        if state is None:
            continue
        candidates.append(
            MemoryReferenceCandidate(
                state=state,
                status="CURRENT"
                if _state_from_snapshot(current_record, uid)
                else "HISTORICAL",
                change_count=sum(event.kind != "HISTORY_GAP" for event in events),
            )
        )
    return tuple(candidates)


__all__ = [
    "MemoryReferenceCandidate",
    "MemoryReferenceState",
    "MemoryReferenceHistoryEvent",
    "collect_reference_candidates",
    "reference_occurrence_events",
]
