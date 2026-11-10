"""Build one immutable Context-scoped slice of canonical History."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    HistoryTransitionKind,
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
    memory_uid: str
    before: ContextHistoryMemoryState | None
    after: ContextHistoryMemoryState | None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
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


__all__ = [
    "ContextHistoryChange",
    "ContextHistoryEvent",
    "ContextHistoryMemoryState",
    "ContextHistorySlice",
    "build_context_history_slice",
    "slice_context_history_from_graph",
]
