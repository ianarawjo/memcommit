"""Project every direct Memory change in one resolved command revision."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...model.memory_event import MemoryHistoryEvent, MemoryHistoryEventKind
from ...verification.frame import _Frame, _ordered_states
from ...verification.model import MemoryHistoryCommandOperation, MemoryState
from ..memory_state_delta import DirectMemoryDelta, direct_memory_deltas
from .model import EffectDerivation


@dataclass(frozen=True)
class CommandRevision:
    """Actual command pre-image/result, independent of the visible log window."""

    checkpoint_uid: str
    timestamp: str
    command: str
    description: str
    before: _Frame
    after: _Frame
    operation_id: str | None = None
    command_operation: MemoryHistoryCommandOperation | None = None


def snapshot_events(
    *,
    revision: CommandRevision,
    annotations: Mapping[str, Mapping[str, Any]] | None,
) -> EffectDerivation:
    before, after = revision.before, revision.after
    deltas = direct_memory_deltas(
        before.memories,
        after.memories,
        before_order=before.order,
        after_order=after.order,
        content=lambda state: state.content,
    )
    events = []
    kinds: dict[str, MemoryHistoryEventKind] = {
        "CREATED": "ADD",
        "EDITED": "EDIT",
        "REMOVED": "REMOVE",
    }
    for delta in sorted(deltas, key=_delta_order):
        details = {} if annotations is None else dict(annotations[delta.memory_uid])
        events.append(
            _event(
                revision,
                kind=kinds[delta.kind],
                before=() if delta.before is None else (delta.before,),
                after=() if delta.after is None else (delta.after,),
                details=details,
            )
        )
    moved = _reordered_memories(before, after)
    if moved:
        events.append(
            _event(
                revision,
                kind="REORDER",
                before=_ordered_states(before, moved),
                after=_ordered_states(after, moved),
                details={},
            )
        )
    return EffectDerivation(events=events)


def _event(
    revision: CommandRevision,
    *,
    kind: MemoryHistoryEventKind,
    before: tuple[MemoryState, ...],
    after: tuple[MemoryState, ...],
    details: dict[str, Any],
) -> MemoryHistoryEvent:
    details.setdefault("operation_id", revision.operation_id)
    details.setdefault("command_operation", revision.command_operation)
    return MemoryHistoryEvent(
        kind=kind,
        command=revision.command,
        checkpoint_uid=revision.checkpoint_uid,
        timestamp=revision.timestamp,
        description=revision.description,
        before=before,
        after=after,
        **details,
    )


def _delta_order(delta: DirectMemoryDelta[MemoryState]) -> tuple[int, int]:
    state = delta.after if delta.after is not None else delta.before
    assert state is not None
    return {"EDITED": 0, "CREATED": 1, "REMOVED": 2}[delta.kind], state.position


def _reordered_memories(before: _Frame, after: _Frame) -> set[str]:
    retained = before.memories.keys() & after.memories.keys()
    before_order = tuple(uid for uid in before.order if uid in retained)
    after_order = tuple(uid for uid in after.order if uid in retained)
    if before_order == after_order:
        return set()
    # Relative ranks exclude shifts caused only by additions or removals.
    before_rank = {uid: position for position, uid in enumerate(before_order)}
    return {
        uid for position, uid in enumerate(after_order) if before_rank[uid] != position
    }
