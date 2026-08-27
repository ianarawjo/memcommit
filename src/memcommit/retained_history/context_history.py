"""Context-wide projection of the shared retained-history timeline."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.context import Context, Memory
from memcommit.retained_history.reconstruction import (
    HistoryEvidence,
    HistoryTimeline,
    HistoryTransitionKind,
    MemoryTransition,
    MemoryVersion,
    build_history,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class ContextTraceMemoryState:
    """One direct Memory endpoint inside a Context history transition."""

    uid: str
    content: str
    position: int

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "content": self.content,
            "position": self.position,
        }


@dataclass(frozen=True)
class ContextTraceChange:
    """One mechanical direct-Memory change in a Context operation."""

    kind: HistoryTransitionKind
    evidence: HistoryEvidence
    memory_uid: str
    before: ContextTraceMemoryState | None
    after: ContextTraceMemoryState | None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "evidence": self.evidence,
            "memory_uid": self.memory_uid,
            "before": self.before.to_dict() if self.before is not None else None,
            "after": self.after.to_dict() if self.after is not None else None,
        }


@dataclass(frozen=True)
class ContextTraceEvent:
    """One retained Context operation and all direct Memory changes it made."""

    checkpoint_uid: str | None
    timestamp: str | None
    command: str
    description: str
    changes: tuple[ContextTraceChange, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "checkpoint_uid": self.checkpoint_uid,
            "timestamp": self.timestamp,
            "command": self.command,
            "description": self.description,
            "changes": [change.to_dict() for change in self.changes],
        }


@dataclass(frozen=True)
class ContextTraceReport:
    """The complete retained direct-state lineage of one exact Context."""

    context_uid: str
    context_name: str
    events: tuple[ContextTraceEvent, ...]
    current: tuple[ContextTraceMemoryState, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "target": "CONTEXT",
            "context": {"uid": self.context_uid, "name": self.context_name},
            "events": [event.to_dict() for event in self.events],
            "current": [state.to_dict() for state in self.current],
            "warnings": list(self.warnings),
        }


def _position(
    timeline: HistoryTimeline,
    *,
    state_index: int,
    memory_uid: str,
) -> int:
    state = timeline.state(state_index)
    return next(
        (
            index
            for index, version in enumerate(state.memories)
            if version.memory_uid == memory_uid
        ),
        -1,
    )


def _memory_state(
    timeline: HistoryTimeline,
    version: MemoryVersion | None,
    *,
    state_index: int,
) -> ContextTraceMemoryState | None:
    if version is None:
        return None
    return ContextTraceMemoryState(
        uid=version.memory_uid,
        content=version.content,
        position=_position(
            timeline,
            state_index=state_index,
            memory_uid=version.memory_uid,
        ),
    )


def _change(
    timeline: HistoryTimeline,
    transition: MemoryTransition,
) -> ContextTraceChange:
    return ContextTraceChange(
        kind=transition.kind,
        evidence=transition.evidence,
        memory_uid=transition.memory_uid,
        before=_memory_state(
            timeline,
            transition.before,
            state_index=transition.from_state_index,
        ),
        after=_memory_state(
            timeline,
            transition.after,
            state_index=transition.to_state_index,
        ),
    )


def context_trace_from_timeline(timeline: HistoryTimeline) -> ContextTraceReport:
    """Group the neutral timeline into complete operation-shaped evidence.

    Checkpoints with no direct Memory delta remain visible because Context
    Trace is an operation lineage, not a concatenation of nonempty Diffs.
    """

    transitions_by_checkpoint: dict[str | None, list[MemoryTransition]] = {}
    for transition in timeline.transitions:
        transitions_by_checkpoint.setdefault(transition.checkpoint_uid, []).append(
            transition
        )

    events = [
        ContextTraceEvent(
            checkpoint_uid=checkpoint.uid,
            timestamp=checkpoint.timestamp,
            command=checkpoint.command,
            description=checkpoint.description,
            changes=tuple(
                _change(timeline, transition)
                for transition in transitions_by_checkpoint.get(checkpoint.uid, ())
            ),
        )
        for checkpoint in timeline.checkpoints
    ]
    live_transitions = transitions_by_checkpoint.get(None, ())
    if live_transitions:
        events.append(
            ContextTraceEvent(
                checkpoint_uid=None,
                timestamp=None,
                command="current",
                description=(
                    "Current Context differs from the last reconstructable "
                    "checkpoint state."
                ),
                changes=tuple(
                    _change(timeline, transition)
                    for transition in live_transitions
                ),
            )
        )

    current_state = next(
        (state for state in reversed(timeline.states) if state.current),
        timeline.states[-1],
    )
    current = tuple(
        ContextTraceMemoryState(
            uid=version.memory_uid,
            content=version.content,
            position=index,
        )
        for index, version in enumerate(current_state.memories)
    )
    return ContextTraceReport(
        context_uid=timeline.context_uid,
        context_name=timeline.context_name,
        events=tuple(events),
        current=current,
        warnings=timeline.warnings,
    )


def build_context_trace(
    store: MemoryStore,
    context_name: str,
) -> ContextTraceReport:
    """Build a Context projection without inventing another history store."""

    return context_trace_from_timeline(build_history(store, context_name))


def current_context_trace(
    context: Context,
    *,
    warnings: tuple[str, ...] = (),
) -> ContextTraceReport:
    """Project current direct content when retained owner history is concealed."""

    current = tuple(
        ContextTraceMemoryState(memory.uid, memory.content, position)
        for position, memory in enumerate(
            item for item in context.iter_items() if isinstance(item, Memory)
        )
    )
    return ContextTraceReport(
        context_uid=context.uid,
        context_name=context.name,
        events=(),
        current=current,
        warnings=warnings,
    )


__all__ = [
    "ContextTraceChange",
    "ContextTraceEvent",
    "ContextTraceMemoryState",
    "ContextTraceReport",
    "build_context_trace",
    "context_trace_from_timeline",
    "current_context_trace",
]
