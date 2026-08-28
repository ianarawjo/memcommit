"""Typed retained provenance for one direct Memory reference occurrence.

A MemoryRef has its own durable identity in the parent Context and points to a
separate Memory identity in a Source Context.  This module keeps those two
histories separate: occurrence events explain why the pointer is present,
while an optional target Trace explains the referenced live Memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.core.context import Context, GrantedMemorySource, MemoryRef
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.retained_record_verification import (
    MemoryHistoryReconstructionError,
)
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.memory_history_construction import (
    MemoryHistory,
    reconstruct_memory_history,
)
from memcommit.persistence.store import MemoryStore


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
class MemoryReferenceTraceEvent:
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


@dataclass(frozen=True)
class MemoryReferenceTraceReport:
    """Occurrence provenance plus an independently authorized target Trace."""

    context_uid: str
    context_name: str
    selected_uid: str
    reference: MemoryReferenceState
    current: bool
    events: tuple[MemoryReferenceTraceEvent, ...]
    target_trace: MemoryHistory | None
    target_history_status: Literal[
        "AVAILABLE",
        "SNAPSHOT_FIXED",
        "UNAVAILABLE",
    ]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "memory_reference",
            "context": {"uid": self.context_uid, "name": self.context_name},
            "selected_uid": self.selected_uid,
            "reference": self.reference.to_dict(),
            "current": self.current,
            "events": [event.to_dict() for event in self.events],
            "target_history_status": self.target_history_status,
            "target_trace": (
                self.target_trace.to_dict() if self.target_trace is not None else None
            ),
            "warnings": list(self.warnings),
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


def _reference_events(
    store: MemoryStore,
    context: Context,
    uid: str,
) -> tuple[tuple[MemoryReferenceTraceEvent, ...], MemoryReferenceState | None]:
    checkpoints = tuple(reversed(store.list_checkpoints(context.name)))
    events: list[MemoryReferenceTraceEvent] = []
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
            MemoryReferenceTraceEvent(
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
            MemoryReferenceTraceEvent(
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
    store: MemoryStore,
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
        events, current = _reference_events(store, context, uid)
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


def _target_trace(
    store: MemoryStore,
    reference: MemoryReferenceState,
) -> tuple[MemoryHistory | None, str | None]:
    owners = tuple(
        context
        for context in store.load_direct_context_graph_strict()
        if context.uid == reference.target_context_uid
    )
    if len(owners) != 1:
        return None, (
            "The live reference target Context is unavailable or ambiguous in "
            "the local Profile."
        )
    owner = owners[0]
    try:
        return reconstruct_memory_history(store, owner, reference.target_memory_uid), None
    except MemoryHistoryReconstructionError as error:
        return None, f"The live reference target history is unavailable: {error}"


def build_reference_trace(
    store: MemoryStore,
    context: Context,
    selector: str,
) -> MemoryReferenceTraceReport:
    """Build one exact MemoryRef occurrence and its authorized target relation."""

    candidates = collect_reference_candidates(store, context)
    matches = tuple(
        candidate
        for candidate in candidates
        if candidate.state.uid.startswith(selector)
    )
    exact = tuple(candidate for candidate in matches if candidate.state.uid == selector)
    if exact:
        matches = exact
    if not matches:
        raise MemoryHistoryReconstructionError(
            f"No Memory reference with uid starting with {selector!r} exists "
            f"in Context {context.name!r} or its retained history."
        )
    if len(matches) != 1:
        raise MemoryHistoryReconstructionError(
            f"Ambiguous prefix {selector!r} matches {len(matches)} Memory references: "
            + ", ".join(candidate.state.uid[:8] for candidate in matches)
        )
    candidate = matches[0]
    events, current = _reference_events(store, context, candidate.state.uid)
    warnings: list[str] = []
    target_trace: MemoryHistory | None = None
    target_status: Literal["AVAILABLE", "SNAPSHOT_FIXED", "UNAVAILABLE"]
    if candidate.state.mode == "SNAPSHOT":
        target_status = "SNAPSHOT_FIXED"
    else:
        target_trace, warning = _target_trace(store, candidate.state)
        target_status = "AVAILABLE" if target_trace is not None else "UNAVAILABLE"
        if warning is not None:
            warnings.append(warning)
    return MemoryReferenceTraceReport(
        context_uid=context.uid,
        context_name=context.name,
        selected_uid=candidate.state.uid,
        reference=candidate.state,
        current=current is not None,
        events=events,
        target_trace=target_trace,
        target_history_status=target_status,
        warnings=tuple(warnings),
    )


__all__ = [
    "MemoryReferenceCandidate",
    "MemoryReferenceState",
    "MemoryReferenceTraceEvent",
    "MemoryReferenceTraceReport",
    "build_reference_trace",
    "collect_reference_candidates",
]
