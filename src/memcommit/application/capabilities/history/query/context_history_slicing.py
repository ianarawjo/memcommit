"""Build one immutable Context-scoped slice of canonical History."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from memcommit.core.context import Context, Memory
from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    HistoryEvidence,
    HistoryTimeline,
    HistoryTransitionKind,
    MemoryTransition,
    MemoryVersion,
)
from memcommit.application.capabilities.history.reconstruction.history_graph_reconstruction import (
    reconstruct_history_graph,
)
from memcommit.application.capabilities.history.model.topology import (
    HistoryEffect,
    HistoryGraph,
    HistoryOccurrence,
)
from memcommit.application.capabilities.history.history_evidence_source import (
    HistoryEvidenceSource,
)


@dataclass(frozen=True)
class ContextHistoryMemoryState:
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
class ContextHistoryChange:
    """One mechanical direct-Memory change in a Context operation."""

    kind: HistoryTransitionKind
    evidence: HistoryEvidence
    memory_uid: str
    before: ContextHistoryMemoryState | None
    after: ContextHistoryMemoryState | None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "evidence": self.evidence,
            "memory_uid": self.memory_uid,
            "before": self.before.to_dict() if self.before is not None else None,
            "after": self.after.to_dict() if self.after is not None else None,
        }


@dataclass(frozen=True)
class ContextHistoryEvent:
    """One retained Context operation and all direct Memory changes it made."""

    checkpoint_uid: str | None
    timestamp: str | None
    command: str
    description: str
    changes: tuple[ContextHistoryChange, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "checkpoint_uid": self.checkpoint_uid,
            "timestamp": self.timestamp,
            "command": self.command,
            "description": self.description,
            "changes": [change.to_dict() for change in self.changes],
        }


@dataclass(frozen=True)
class ContextHistorySlice:
    """The complete retained direct-state lineage of one exact Context."""

    context_uid: str
    context_name: str
    events: tuple[ContextHistoryEvent, ...]
    current: tuple[ContextHistoryMemoryState, ...]
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
) -> ContextHistoryMemoryState | None:
    if version is None:
        return None
    return ContextHistoryMemoryState(
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
) -> ContextHistoryChange:
    return ContextHistoryChange(
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


def slice_context_history_from_timeline(timeline: HistoryTimeline) -> ContextHistorySlice:
    """Group the neutral timeline into complete operation-shaped evidence.

    Checkpoints with no direct Memory delta remain visible because Context
    History is an operation lineage, not a concatenation of nonempty Diffs.
    """

    transitions_by_checkpoint: dict[str | None, list[MemoryTransition]] = {}
    for transition in timeline.transitions:
        transitions_by_checkpoint.setdefault(transition.checkpoint_uid, []).append(
            transition
        )

    events = [
        ContextHistoryEvent(
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
            ContextHistoryEvent(
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
        ContextHistoryMemoryState(
            uid=version.memory_uid,
            content=version.content,
            position=index,
        )
        for index, version in enumerate(current_state.memories)
    )
    return ContextHistorySlice(
        context_uid=timeline.context_uid,
        context_name=timeline.context_name,
        events=tuple(events),
        current=current,
        warnings=timeline.warnings,
    )


def _projected_memory_state(
    occurrence: HistoryOccurrence | None,
) -> ContextHistoryMemoryState | None:
    if occurrence is None:
        return None
    if occurrence.kind != "MEMORY" or occurrence.position is None:
        raise ValueError("Context History effect does not point to a Memory state.")
    if occurrence.content is None:
        raise ValueError("Context History Memory state has no retained content.")
    return ContextHistoryMemoryState(
        uid=occurrence.subject_uid,
        content=occurrence.content,
        position=occurrence.position,
    )


def _projected_context_change(
    lineage: HistoryGraph,
    effect: HistoryEffect,
) -> ContextHistoryChange:
    before = (
        lineage.occurrence(effect.before_occurrence_ids[0])
        if effect.before_occurrence_ids
        else None
    )
    after = (
        lineage.occurrence(effect.after_occurrence_ids[0])
        if effect.after_occurrence_ids
        else None
    )
    if len(effect.before_occurrence_ids) > 1 or len(effect.after_occurrence_ids) > 1:
        raise ValueError("One Context History change must affect one Memory identity.")
    memory = after or before
    if memory is None:
        raise ValueError("Context History change has no Memory endpoint.")
    return ContextHistoryChange(
        kind=cast(HistoryTransitionKind, effect.kind),
        evidence=cast(HistoryEvidence, effect.evidence),
        memory_uid=memory.subject_uid,
        before=_projected_memory_state(before),
        after=_projected_memory_state(after),
    )


def slice_context_history_from_graph(graph: HistoryGraph) -> ContextHistorySlice:
    """Project the root Context from the shared operation/occurrence graph."""

    effects_by_step: dict[str, list[HistoryEffect]] = {}
    for effect in graph.effects:
        if effect.channel == "CONTEXT":
            effects_by_step.setdefault(effect.operation_step_id, []).append(effect)
    events = tuple(
        ContextHistoryEvent(
            checkpoint_uid=step.checkpoint_uid,
            timestamp=step.timestamp,
            command=step.command,
            description=step.description,
            changes=tuple(
                _projected_context_change(graph, effect)
                for effect in effects_by_step.get(step.node_id, ())
            ),
        )
        for step_id in graph.context_step_ids
        for step in (graph.step(step_id),)
    )
    current_ids = {
        relation.target_node_id
        for relation in graph.relations
        if relation.kind == "CONTAINS"
        and relation.source_node_id == graph.current_context_occurrence_id
    }
    current_occurrences = tuple(
        sorted(
            (
                graph.occurrence(node_id)
                for node_id in current_ids
                if graph.occurrence(node_id).kind == "MEMORY"
            ),
            key=lambda occurrence: (
                occurrence.position
                if occurrence.position is not None
                else 2**63,
                occurrence.subject_uid,
            ),
        )
    )
    return ContextHistorySlice(
        context_uid=graph.root_context_uid,
        context_name=graph.root_context_name,
        events=events,
        current=tuple(
            state
            for occurrence in current_occurrences
            for state in (_projected_memory_state(occurrence),)
            if state is not None
        ),
        warnings=graph.context_warnings,
    )


def build_context_history_slice(
    store: HistoryEvidenceSource,
    context_name: str,
) -> ContextHistorySlice:
    """Build one Context slice from the canonical History graph."""

    context = store.load_direct(context_name)
    return slice_context_history_from_graph(
        reconstruct_history_graph(store, context).graph
    )


def current_context_history_slice(
    context: Context,
    *,
    warnings: tuple[str, ...] = (),
) -> ContextHistorySlice:
    """Project current direct content when retained owner history is concealed."""

    current = tuple(
        ContextHistoryMemoryState(memory.uid, memory.content, position)
        for position, memory in enumerate(
            item for item in context.iter_items() if isinstance(item, Memory)
        )
    )
    return ContextHistorySlice(
        context_uid=context.uid,
        context_name=context.name,
        events=(),
        current=current,
        warnings=warnings,
    )


__all__ = [
    "ContextHistoryChange",
    "ContextHistoryEvent",
    "ContextHistoryMemoryState",
    "ContextHistorySlice",
    "build_context_history_slice",
    "slice_context_history_from_graph",
    "slice_context_history_from_timeline",
    "current_context_history_slice",
]
