"""Reconstruct one complete canonical History graph from verified evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from memcommit.application.capabilities.history.verification import (
    MemoryState,
    _Frame,
    _checkpoint_entries,
)
from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    HistoryTimeline,
    MemoryTransition,
    build_history,
)
from memcommit.application.capabilities.history.reconstruction.reference_occurrence_derivation import (
    MemoryReferenceCandidate,
    MemoryReferenceState,
    MemoryReferenceHistoryEvent,
    collect_reference_candidates,
    reference_occurrence_events,
)
from memcommit.application.capabilities.history.model.topology import (
    HistoryEffect,
    HistoryEvidence,
    HistoryGraph,
    HistoryOccurrence,
    HistoryOperation,
    HistoryStep,
    HistoryRelation,
)
from memcommit.application.capabilities.history.reconstruction.memory_effect_derivation import (
    MemoryHistoryEvent,
    derive_memory_history_events,
)
from memcommit.core.context import Context
from memcommit.application.capabilities.history.history_evidence_source import (
    HistoryEvidenceSource,
)


@dataclass(frozen=True, slots=True)
class HistoryGraphAssembly:
    """Shared topology plus exact verified payloads used by public projections."""

    graph: HistoryGraph
    timeline: HistoryTimeline
    memory_events: tuple[MemoryHistoryEvent, ...]
    memory_frames: tuple[_Frame, ...]
    reference_evidence: tuple["HistoryReferenceEvidence", ...] = ()


@dataclass(frozen=True, slots=True)
class HistoryReferenceEvidence:
    """Exact retained occurrence payload behind one Reference projection."""

    candidate: MemoryReferenceCandidate
    events: tuple[MemoryReferenceHistoryEvent, ...]
    current: MemoryReferenceState | None


@dataclass
class _OperationAccumulator:
    operation_uid: str | None
    checkpoint_uids: list[str]
    context_uids: list[str]
    sequence: int


class _Draft:
    def __init__(self) -> None:
        self.operations: dict[str, _OperationAccumulator] = {}
        self.steps: dict[str, HistoryStep] = {}
        self.occurrences: dict[str, HistoryOccurrence] = {}
        self.effects: list[HistoryEffect] = []
        self.relations: dict[str, HistoryRelation] = {}

    def register_operation(
        self,
        *,
        node_id: str,
        operation_uid: str | None,
        checkpoint_uid: str | None,
        context_uid: str,
        sequence: int,
    ) -> None:
        operation = self.operations.setdefault(
            node_id,
            _OperationAccumulator(
                operation_uid=operation_uid,
                checkpoint_uids=[],
                context_uids=[],
                sequence=sequence,
            ),
        )
        if checkpoint_uid is not None and checkpoint_uid not in operation.checkpoint_uids:
            operation.checkpoint_uids.append(checkpoint_uid)
        if context_uid not in operation.context_uids:
            operation.context_uids.append(context_uid)

    def add_occurrence(self, occurrence: HistoryOccurrence) -> None:
        existing = self.occurrences.get(occurrence.node_id)
        if existing is not None and existing != occurrence:
            raise ValueError("One History occurrence identity has conflicting evidence.")
        self.occurrences[occurrence.node_id] = occurrence

    def add_relation(self, relation: HistoryRelation) -> None:
        existing = self.relations.get(relation.relation_id)
        if existing is not None and existing != relation:
            raise ValueError("One History relation identity has conflicting evidence.")
        self.relations[relation.relation_id] = relation


def _event_operation_uid(event: MemoryHistoryEvent) -> str | None:
    if event.command_operation is not None:
        return event.command_operation.uid
    return event.operation_id


def _operation_uids_by_checkpoint(
    events: Iterable[MemoryHistoryEvent],
) -> dict[str, str]:
    candidates: dict[str, set[str]] = {}
    for event in events:
        operation_uid = _event_operation_uid(event)
        if event.checkpoint_uid is None or operation_uid is None:
            continue
        candidates.setdefault(event.checkpoint_uid, set()).add(operation_uid)
    # Conflicting retained identifiers are not guessed into one operation.
    return {
        checkpoint_uid: next(iter(operation_uids))
        for checkpoint_uid, operation_uids in candidates.items()
        if len(operation_uids) == 1
    }


def _operation_node_id(
    *,
    context_uid: str,
    checkpoint_uid: str | None,
    operation_uid: str | None,
    sequence: int,
) -> str:
    if operation_uid is not None:
        return f"operation:{operation_uid}"
    if checkpoint_uid is not None:
        return f"checkpoint-operation:{context_uid}:{checkpoint_uid}"
    return f"current-operation:{context_uid}:{sequence}"


def _step_node_id(
    *,
    context_uid: str,
    checkpoint_uid: str | None,
    sequence: int,
    operation_uid: str | None,
) -> str:
    checkpoint_part = checkpoint_uid if checkpoint_uid is not None else "current"
    operation_part = operation_uid if operation_uid is not None else "checkpoint"
    return f"operation-step:{context_uid}:{checkpoint_part}:{operation_part}:{sequence}"


def _register_step(
    draft: _Draft,
    *,
    context_uid: str,
    context_name: str,
    checkpoint_uid: str | None,
    timestamp: str | None,
    command: str,
    description: str,
    evidence: HistoryEvidence,
    sequence: int,
    operation_uid: str | None,
) -> HistoryStep:
    operation_node_id = _operation_node_id(
        context_uid=context_uid,
        checkpoint_uid=checkpoint_uid,
        operation_uid=operation_uid,
        sequence=sequence,
    )
    draft.register_operation(
        node_id=operation_node_id,
        operation_uid=operation_uid,
        checkpoint_uid=checkpoint_uid,
        context_uid=context_uid,
        sequence=sequence,
    )
    step = HistoryStep(
        node_id=_step_node_id(
            context_uid=context_uid,
            checkpoint_uid=checkpoint_uid,
            sequence=sequence,
            operation_uid=operation_uid,
        ),
        operation_node_id=operation_node_id,
        context_uid=context_uid,
        context_name=context_name,
        checkpoint_uid=checkpoint_uid,
        timestamp=timestamp,
        command=command,
        description=description,
        evidence=evidence,
        sequence=sequence,
    )
    draft.steps[step.node_id] = step
    return step


def _context_occurrence_id(context_uid: str, state_anchor: str) -> str:
    return f"context-occurrence:{context_uid}:{state_anchor}"


def _memory_occurrence_id(
    context_uid: str,
    state_anchor: str,
    memory_uid: str,
) -> str:
    return f"memory-occurrence:{context_uid}:{state_anchor}:{memory_uid}"


def _add_context_states(draft: _Draft, timeline: HistoryTimeline) -> None:
    for state in timeline.states:
        state_anchor = f"history-state:{state.index}:{state.record_digest}"
        context_occurrence_id = _context_occurrence_id(
            timeline.context_uid,
            state_anchor,
        )
        draft.add_occurrence(
            HistoryOccurrence(
                node_id=context_occurrence_id,
                kind="CONTEXT",
                context_uid=timeline.context_uid,
                context_name=timeline.context_name,
                subject_uid=timeline.context_uid,
                state_anchor=state_anchor,
                selectable=False,
            )
        )
        for position, version in enumerate(state.memories):
            memory_occurrence_id = _memory_occurrence_id(
                timeline.context_uid,
                state_anchor,
                version.memory_uid,
            )
            draft.add_occurrence(
                HistoryOccurrence(
                    node_id=memory_occurrence_id,
                    kind="MEMORY",
                    context_uid=timeline.context_uid,
                    context_name=timeline.context_name,
                    subject_uid=version.memory_uid,
                    state_anchor=state_anchor,
                    content=version.content,
                    content_digest=version.content_digest,
                    position=position,
                    selectable=True,
                )
            )
            draft.add_relation(
                HistoryRelation(
                    relation_id=(
                        f"contains:{context_occurrence_id}:{memory_occurrence_id}"
                    ),
                    kind="CONTAINS",
                    source_node_id=context_occurrence_id,
                    target_node_id=memory_occurrence_id,
                )
            )


def _timeline_memory_occurrence_id(
    timeline: HistoryTimeline,
    *,
    state_index: int,
    memory_uid: str,
) -> str:
    state = timeline.state(state_index)
    return _memory_occurrence_id(
        timeline.context_uid,
        f"history-state:{state.index}:{state.record_digest}",
        memory_uid,
    )


def _add_context_effect(
    draft: _Draft,
    timeline: HistoryTimeline,
    transition: MemoryTransition,
    step: HistoryStep,
) -> None:
    before_ids = (
        (
            _timeline_memory_occurrence_id(
                timeline,
                state_index=transition.from_state_index,
                memory_uid=transition.memory_uid,
            ),
        )
        if transition.before is not None
        else ()
    )
    after_ids = (
        (
            _timeline_memory_occurrence_id(
                timeline,
                state_index=transition.to_state_index,
                memory_uid=transition.memory_uid,
            ),
        )
        if transition.after is not None
        else ()
    )
    effect = HistoryEffect(
        effect_id=f"context-effect:{timeline.context_uid}:{transition.index}",
        channel="CONTEXT",
        operation_node_id=step.operation_node_id,
        operation_step_id=step.node_id,
        kind=transition.kind,
        evidence=transition.evidence,
        before_occurrence_ids=before_ids,
        after_occurrence_ids=after_ids,
    )
    draft.effects.append(effect)
    for index, occurrence_id in enumerate(before_ids):
        draft.add_relation(
            HistoryRelation(
                relation_id=f"input:{effect.effect_id}:{index}",
                kind="INPUT",
                source_node_id=occurrence_id,
                target_node_id=step.operation_node_id,
                operation_node_id=step.operation_node_id,
                operation_step_id=step.node_id,
                effect_id=effect.effect_id,
            )
        )
    for index, occurrence_id in enumerate(after_ids):
        draft.add_relation(
            HistoryRelation(
                relation_id=f"output:{effect.effect_id}:{index}",
                kind="OUTPUT",
                source_node_id=step.operation_node_id,
                target_node_id=occurrence_id,
                operation_node_id=step.operation_node_id,
                operation_step_id=step.node_id,
                effect_id=effect.effect_id,
            )
        )
    if before_ids and after_ids:
        draft.add_relation(
            HistoryRelation(
                relation_id=f"continues:{effect.effect_id}:0:0",
                kind="CONTINUES_AS",
                source_node_id=before_ids[0],
                target_node_id=after_ids[0],
                operation_node_id=step.operation_node_id,
                operation_step_id=step.node_id,
                effect_id=effect.effect_id,
            )
        )


def _matching_state_context(
    state: MemoryState,
    frames: tuple[_Frame, ...],
    *,
    after: bool,
    fallback_uid: str,
    fallback_name: str,
) -> tuple[str, str]:
    matches = tuple(
        (frame.context_uid, frame.context_name)
        for frame in frames
        if state.uid in frame.memories
        and frame.memories[state.uid].content_digest == state.content_digest
    )
    if not matches:
        return fallback_uid, fallback_name
    return matches[-1] if after else matches[0]


def _event_state_context(
    event: MemoryHistoryEvent,
    state: MemoryState,
    *,
    before_index: int | None,
    after: bool,
    frames: tuple[_Frame, ...],
    fallback_uid: str,
    fallback_name: str,
) -> tuple[str, str]:
    transition = event.context_transition
    if transition is not None:
        if event.kind == "BRANCHED":
            owner = transition.target if after else transition.source
            return owner.uid, owner.name
        if event.kind == "MERGED_IN":
            if after or (before_index is not None and before_index > 0):
                return transition.target.uid, transition.target.name
            return transition.source.uid, transition.source.name
    return _matching_state_context(
        state,
        frames,
        after=after,
        fallback_uid=fallback_uid,
        fallback_name=fallback_name,
    )


def _add_memory_frame_occurrences(
    draft: _Draft,
    frames: tuple[_Frame, ...],
) -> None:
    for frame_index, frame in enumerate(frames):
        state_anchor = f"memory-frame:{frame_index}:{frame.record_digest}"
        context_occurrence_id = _context_occurrence_id(
            frame.context_uid,
            state_anchor,
        )
        draft.add_occurrence(
            HistoryOccurrence(
                node_id=context_occurrence_id,
                kind="CONTEXT",
                context_uid=frame.context_uid,
                context_name=frame.context_name,
                subject_uid=frame.context_uid,
                state_anchor=state_anchor,
            )
        )
        for uid in frame.order:
            state = frame.memories[uid]
            occurrence_id = _memory_occurrence_id(
                frame.context_uid,
                state_anchor,
                uid,
            )
            draft.add_occurrence(
                HistoryOccurrence(
                    node_id=occurrence_id,
                    kind="MEMORY",
                    context_uid=frame.context_uid,
                    context_name=frame.context_name,
                    subject_uid=uid,
                    state_anchor=state_anchor,
                    content=state.content,
                    content_digest=state.content_digest,
                    position=state.position,
                    selectable=True,
                )
            )
            draft.add_relation(
                HistoryRelation(
                    relation_id=f"contains:{context_occurrence_id}:{occurrence_id}",
                    kind="CONTAINS",
                    source_node_id=context_occurrence_id,
                    target_node_id=occurrence_id,
                )
            )


_DERIVED_EVENT_KINDS = frozenset(
    {"SPLIT", "ABSORBED", "TRANSLATED", "BRANCHED", "MERGED_IN"}
)


def _add_memory_effect(
    draft: _Draft,
    *,
    event: MemoryHistoryEvent,
    event_index: int,
    step: HistoryStep,
    frames: tuple[_Frame, ...],
    fallback_uid: str,
    fallback_name: str,
) -> None:
    before_ids: list[str] = []
    after_ids: list[str] = []
    effect_id = f"memory-effect:{fallback_uid}:{event_index}"
    for before_index, state in enumerate(event.before):
        context_uid, context_name = _event_state_context(
            event,
            state,
            before_index=before_index,
            after=False,
            frames=frames,
            fallback_uid=fallback_uid,
            fallback_name=fallback_name,
        )
        state_anchor = f"event:{event_index}:before:{before_index}"
        occurrence_id = _memory_occurrence_id(
            context_uid,
            state_anchor,
            state.uid,
        )
        draft.add_occurrence(
            HistoryOccurrence(
                node_id=occurrence_id,
                kind="MEMORY",
                context_uid=context_uid,
                context_name=context_name,
                subject_uid=state.uid,
                state_anchor=state_anchor,
                content=state.content,
                content_digest=state.content_digest,
                position=state.position,
                selectable=True,
            )
        )
        before_ids.append(occurrence_id)
    for after_index, state in enumerate(event.after):
        context_uid, context_name = _event_state_context(
            event,
            state,
            before_index=None,
            after=True,
            frames=frames,
            fallback_uid=fallback_uid,
            fallback_name=fallback_name,
        )
        state_anchor = f"event:{event_index}:after:{after_index}"
        occurrence_id = _memory_occurrence_id(
            context_uid,
            state_anchor,
            state.uid,
        )
        draft.add_occurrence(
            HistoryOccurrence(
                node_id=occurrence_id,
                kind="MEMORY",
                context_uid=context_uid,
                context_name=context_name,
                subject_uid=state.uid,
                state_anchor=state_anchor,
                content=state.content,
                content_digest=state.content_digest,
                position=state.position,
                selectable=True,
            )
        )
        after_ids.append(occurrence_id)
    effect = HistoryEffect(
        effect_id=effect_id,
        channel="MEMORY",
        operation_node_id=step.operation_node_id,
        operation_step_id=step.node_id,
        kind=event.kind,
        evidence=event.evidence,
        before_occurrence_ids=tuple(before_ids),
        after_occurrence_ids=tuple(after_ids),
        payload_index=event_index,
    )
    draft.effects.append(effect)
    for index, occurrence_id in enumerate(before_ids):
        draft.add_relation(
            HistoryRelation(
                relation_id=f"input:{effect_id}:{index}",
                kind="INPUT",
                source_node_id=occurrence_id,
                target_node_id=step.operation_node_id,
                operation_node_id=step.operation_node_id,
                operation_step_id=step.node_id,
                effect_id=effect_id,
            )
        )
    for index, occurrence_id in enumerate(after_ids):
        draft.add_relation(
            HistoryRelation(
                relation_id=f"output:{effect_id}:{index}",
                kind="OUTPUT",
                source_node_id=step.operation_node_id,
                target_node_id=occurrence_id,
                operation_node_id=step.operation_node_id,
                operation_step_id=step.node_id,
                effect_id=effect_id,
            )
        )
    for before_index, before_id in enumerate(before_ids):
        for after_index, after_id in enumerate(after_ids):
            before_uid = draft.occurrences[before_id].subject_uid
            after_uid = draft.occurrences[after_id].subject_uid
            if before_uid == after_uid:
                draft.add_relation(
                    HistoryRelation(
                        relation_id=(
                            f"continues:{effect_id}:{before_index}:{after_index}"
                        ),
                        kind="CONTINUES_AS",
                        source_node_id=before_id,
                        target_node_id=after_id,
                        operation_node_id=step.operation_node_id,
                        operation_step_id=step.node_id,
                        effect_id=effect_id,
                    )
                )
            if event.kind in _DERIVED_EVENT_KINDS:
                draft.add_relation(
                    HistoryRelation(
                        relation_id=(
                            f"derived:{effect_id}:{before_index}:{after_index}"
                        ),
                        kind="DERIVED_FROM",
                        source_node_id=before_id,
                        target_node_id=after_id,
                        operation_node_id=step.operation_node_id,
                        operation_step_id=step.node_id,
                        effect_id=effect_id,
                    )
                )


def _add_reference_occurrence(
    draft: _Draft,
    *,
    state: MemoryReferenceState,
    context_uid: str,
    context_name: str,
    state_anchor: str,
) -> str:
    occurrence_id = (
        f"memory-reference-occurrence:{context_uid}:{state_anchor}:{state.uid}"
    )
    draft.add_occurrence(
        HistoryOccurrence(
            node_id=occurrence_id,
            kind="MEMORY_REFERENCE",
            context_uid=context_uid,
            context_name=context_name,
            subject_uid=state.uid,
            state_anchor=state_anchor,
            position=state.position,
        )
    )
    target_id = (
        f"memory-target-occurrence:{state.target_context_uid}:"
        f"{state_anchor}:{state.uid}:{state.target_memory_uid}"
    )
    draft.add_occurrence(
        HistoryOccurrence(
            node_id=target_id,
            kind="MEMORY",
            context_uid=state.target_context_uid,
            context_name=state.target_context_name,
            subject_uid=state.target_memory_uid,
            state_anchor=f"relationship-target:{state_anchor}:{state.uid}",
            content=state.snapshot_content,
            content_digest=state.snapshot_content_sha256,
            selectable=False,
        )
    )
    relation_kind = "REFERENCES" if state.mode == "SNAPSHOT" else "EMBEDS"
    draft.add_relation(
        HistoryRelation(
            relation_id=f"{relation_kind.lower()}:{occurrence_id}:{target_id}",
            kind=relation_kind,
            source_node_id=occurrence_id,
            target_node_id=target_id,
        )
    )
    return occurrence_id


def _add_reference_effect(
    draft: _Draft,
    *,
    event: MemoryReferenceHistoryEvent,
    payload_index: int,
    step: HistoryStep,
    context_uid: str,
    context_name: str,
) -> None:
    effect_id = f"reference-effect:{context_uid}:{payload_index}"
    before_ids = (
        (
            _add_reference_occurrence(
                draft,
                state=event.before,
                context_uid=context_uid,
                context_name=context_name,
                state_anchor=f"reference-event:{payload_index}:before",
            ),
        )
        if event.before is not None
        else ()
    )
    after_ids = (
        (
            _add_reference_occurrence(
                draft,
                state=event.after,
                context_uid=context_uid,
                context_name=context_name,
                state_anchor=f"reference-event:{payload_index}:after",
            ),
        )
        if event.after is not None
        else ()
    )
    effect = HistoryEffect(
        effect_id=effect_id,
        channel="REFERENCE",
        operation_node_id=step.operation_node_id,
        operation_step_id=step.node_id,
        kind=event.kind,
        evidence=event.evidence,
        before_occurrence_ids=before_ids,
        after_occurrence_ids=after_ids,
        payload_index=payload_index,
    )
    draft.effects.append(effect)
    for index, occurrence_id in enumerate(before_ids):
        draft.add_relation(
            HistoryRelation(
                relation_id=f"input:{effect_id}:{index}",
                kind="INPUT",
                source_node_id=occurrence_id,
                target_node_id=step.operation_node_id,
                operation_node_id=step.operation_node_id,
                operation_step_id=step.node_id,
                effect_id=effect_id,
            )
        )
    for index, occurrence_id in enumerate(after_ids):
        draft.add_relation(
            HistoryRelation(
                relation_id=f"output:{effect_id}:{index}",
                kind="OUTPUT",
                source_node_id=step.operation_node_id,
                target_node_id=occurrence_id,
                operation_node_id=step.operation_node_id,
                operation_step_id=step.node_id,
                effect_id=effect_id,
            )
        )
    if before_ids and after_ids:
        draft.add_relation(
            HistoryRelation(
                relation_id=f"continues:{effect_id}:0:0",
                kind="CONTINUES_AS",
                source_node_id=before_ids[0],
                target_node_id=after_ids[0],
                operation_node_id=step.operation_node_id,
                operation_step_id=step.node_id,
                effect_id=effect_id,
            )
        )


def _ordered_item_uids(record: dict[str, object]) -> tuple[str, ...]:
    serialized = record.get("memories")
    if not isinstance(serialized, dict):
        return ()
    requested = record.get("order")
    result: list[str] = []
    seen: set[str] = set()
    if isinstance(requested, list):
        for uid in requested:
            if isinstance(uid, str) and uid in serialized and uid not in seen:
                result.append(uid)
                seen.add(uid)
    for uid in serialized:
        if isinstance(uid, str) and uid not in seen:
            result.append(uid)
            seen.add(uid)
    return tuple(result)


def _relationship_target(
    item: dict[str, object],
) -> tuple[str, str, str, str] | None:
    kind = item.get("type")
    if kind in {"memory_ref", "granted_memory_ref", "memory_snapshot_ref"}:
        target = item.get("target_context")
        target_memory_uid = item.get("target_memory_uid")
        if not isinstance(target, dict) or not isinstance(target_memory_uid, str):
            return None
        context_uid = target.get("uid")
        context_name = target.get("name")
        if not isinstance(context_uid, str) or not isinstance(context_name, str):
            return None
        relation_kind = "REFERENCES" if kind == "memory_snapshot_ref" else "EMBEDS"
        return relation_kind, context_uid, context_name, target_memory_uid
    return None


def _context_relationship_target(
    item: dict[str, object],
) -> tuple[str, str, str] | None:
    kind = item.get("type")
    if kind in {"context_ref", "granted_context_ref"}:
        uid = item.get("uid")
        name = item.get("name")
        if isinstance(uid, str) and isinstance(name, str):
            return "EMBEDS", uid, name
    if kind == "context_snapshot_ref":
        target = item.get("target_context")
        if isinstance(target, dict):
            uid = target.get("uid")
            name = target.get("name")
            if isinstance(uid, str) and isinstance(name, str):
                return "REFERENCES", uid, name
    return None


def _add_relationship_state(
    draft: _Draft,
    *,
    record: dict[str, object],
    owner_context_uid: str,
    owner_context_name: str,
    state_anchor: str,
    operation_step: HistoryStep | None,
) -> None:
    serialized = record.get("memories")
    if not isinstance(serialized, dict):
        return
    owner_id = _context_occurrence_id(owner_context_uid, state_anchor)
    if owner_id not in draft.occurrences:
        return
    for position, item_uid in enumerate(_ordered_item_uids(record)):
        item = serialized.get(item_uid)
        if not isinstance(item, dict):
            continue
        memory_target = _relationship_target(item)
        if memory_target is not None:
            relation_kind, target_context_uid, target_context_name, target_uid = (
                memory_target
            )
            relationship_id = (
                f"memory-reference-occurrence:{owner_context_uid}:"
                f"{state_anchor}:{item_uid}"
            )
            target_id = (
                f"memory-target-occurrence:{target_context_uid}:"
                f"{state_anchor}:{item_uid}:{target_uid}"
            )
            draft.add_occurrence(
                HistoryOccurrence(
                    node_id=relationship_id,
                    kind="MEMORY_REFERENCE",
                    context_uid=owner_context_uid,
                    context_name=owner_context_name,
                    subject_uid=item_uid,
                    state_anchor=state_anchor,
                    position=position,
                )
            )
            draft.add_occurrence(
                HistoryOccurrence(
                    node_id=target_id,
                    kind="MEMORY",
                    context_uid=target_context_uid,
                    context_name=target_context_name,
                    subject_uid=target_uid,
                    state_anchor=f"relationship-target:{state_anchor}:{item_uid}",
                    selectable=False,
                )
            )
            draft.add_relation(
                HistoryRelation(
                    relation_id=f"contains:{owner_id}:{relationship_id}",
                    kind="CONTAINS",
                    source_node_id=owner_id,
                    target_node_id=relationship_id,
                    operation_node_id=(
                        operation_step.operation_node_id
                        if operation_step is not None
                        else None
                    ),
                    operation_step_id=(
                        operation_step.node_id if operation_step is not None else None
                    ),
                )
            )
            draft.add_relation(
                HistoryRelation(
                    relation_id=f"{relation_kind.lower()}:{relationship_id}:{target_id}",
                    kind=relation_kind,
                    source_node_id=relationship_id,
                    target_node_id=target_id,
                    operation_node_id=(
                        operation_step.operation_node_id
                        if operation_step is not None
                        else None
                    ),
                    operation_step_id=(
                        operation_step.node_id if operation_step is not None else None
                    ),
                )
            )
            continue
        context_target = _context_relationship_target(item)
        if context_target is None:
            continue
        relation_kind, target_context_uid, target_context_name = context_target
        target_id = (
            f"context-target-occurrence:{target_context_uid}:"
            f"{state_anchor}:{item_uid}"
        )
        draft.add_occurrence(
            HistoryOccurrence(
                node_id=target_id,
                kind="CONTEXT",
                context_uid=target_context_uid,
                context_name=target_context_name,
                subject_uid=target_context_uid,
                state_anchor=f"relationship-target:{state_anchor}:{item_uid}",
            )
        )
        draft.add_relation(
            HistoryRelation(
                relation_id=f"{relation_kind.lower()}:{owner_id}:{target_id}",
                kind=relation_kind,
                source_node_id=owner_id,
                target_node_id=target_id,
                operation_node_id=(
                    operation_step.operation_node_id
                    if operation_step is not None
                    else None
                ),
                operation_step_id=(
                    operation_step.node_id if operation_step is not None else None
                ),
            )
        )


def reconstruct_history_graph_from_evidence(
    *,
    timeline: HistoryTimeline,
    memory_events: Iterable[MemoryHistoryEvent],
    memory_frames: Iterable[_Frame],
    retained_entries: Iterable[dict[str, object]] = (),
    current_record: dict[str, object] | None = None,
    memory_warnings: Iterable[str] = (),
    reference_evidence: Iterable[HistoryReferenceEvidence] = (),
) -> HistoryGraphAssembly:
    """Normalize already verified evidence without interpreting report prose."""

    events = tuple(memory_events)
    frames = tuple(memory_frames)
    entries = tuple(retained_entries)
    references = tuple(reference_evidence)
    operation_uid_by_checkpoint = _operation_uids_by_checkpoint(events)
    draft = _Draft()
    _add_context_states(draft, timeline)
    _add_memory_frame_occurrences(draft, frames)

    steps_by_checkpoint: dict[str | None, HistoryStep] = {}
    for checkpoint_sequence, checkpoint in enumerate(timeline.checkpoints):
        step = _register_step(
            draft,
            context_uid=timeline.context_uid,
            context_name=timeline.context_name,
            checkpoint_uid=checkpoint.uid,
            timestamp=checkpoint.timestamp,
            command=checkpoint.command,
            description=checkpoint.description,
            evidence="RECORDED",
            sequence=checkpoint_sequence,
            operation_uid=operation_uid_by_checkpoint.get(checkpoint.uid),
        )
        steps_by_checkpoint[checkpoint.uid] = step

    live_transitions = tuple(
        transition
        for transition in timeline.transitions
        if transition.checkpoint_uid is None
    )
    if live_transitions:
        first = live_transitions[0]
        step = _register_step(
            draft,
            context_uid=timeline.context_uid,
            context_name=timeline.context_name,
            checkpoint_uid=None,
            timestamp=None,
            command=first.command,
            description=first.description,
            evidence="UNRECORDED",
            sequence=len(draft.steps),
            operation_uid=None,
        )
        steps_by_checkpoint[None] = step

    context_step_ids = tuple(
        step.node_id
        for checkpoint_uid, step in steps_by_checkpoint.items()
        if checkpoint_uid is not None
    ) + (
        (steps_by_checkpoint[None].node_id,)
        if None in steps_by_checkpoint
        else ()
    )

    for transition in timeline.transitions:
        step = steps_by_checkpoint.get(transition.checkpoint_uid)
        if step is None:
            step = _register_step(
                draft,
                context_uid=timeline.context_uid,
                context_name=timeline.context_name,
                checkpoint_uid=transition.checkpoint_uid,
                timestamp=transition.timestamp,
                command=transition.command,
                description=transition.description,
                evidence=transition.evidence,
                sequence=len(draft.steps),
                operation_uid=(
                    operation_uid_by_checkpoint.get(transition.checkpoint_uid)
                    if transition.checkpoint_uid is not None
                    else None
                ),
            )
            steps_by_checkpoint[transition.checkpoint_uid] = step
        _add_context_effect(draft, timeline, transition, step)

    for event_index, event in enumerate(events):
        event_operation_uid = _event_operation_uid(event)
        step = steps_by_checkpoint.get(event.checkpoint_uid)
        if step is None or (
            event_operation_uid is not None
            and step.operation_node_id
            != _operation_node_id(
                context_uid=timeline.context_uid,
                checkpoint_uid=event.checkpoint_uid,
                operation_uid=event_operation_uid,
                sequence=step.sequence,
            )
        ):
            step = _register_step(
                draft,
                context_uid=timeline.context_uid,
                context_name=timeline.context_name,
                checkpoint_uid=event.checkpoint_uid,
                timestamp=event.timestamp,
                command=event.command,
                description=event.description,
                evidence=event.evidence,
                sequence=len(draft.steps),
                operation_uid=event_operation_uid,
            )
            if event.checkpoint_uid not in steps_by_checkpoint:
                steps_by_checkpoint[event.checkpoint_uid] = step
        if event.command_operation is not None:
            for operation_context in event.command_operation.contexts:
                draft.register_operation(
                    node_id=step.operation_node_id,
                    operation_uid=event.command_operation.uid,
                    checkpoint_uid=event.checkpoint_uid,
                    context_uid=operation_context.uid,
                    sequence=step.sequence,
                )
        _add_memory_effect(
            draft,
            event=event,
            event_index=event_index,
            step=step,
            frames=frames,
            fallback_uid=timeline.context_uid,
            fallback_name=timeline.context_name,
        )

    reference_payload_index = 0
    for evidence in references:
        for event in evidence.events:
            step = steps_by_checkpoint.get(event.checkpoint_uid)
            if step is None:
                step = _register_step(
                    draft,
                    context_uid=timeline.context_uid,
                    context_name=timeline.context_name,
                    checkpoint_uid=event.checkpoint_uid,
                    timestamp=event.timestamp,
                    command=event.command,
                    description=event.description,
                    evidence=event.evidence,
                    sequence=len(draft.steps),
                    operation_uid=None,
                )
                steps_by_checkpoint[event.checkpoint_uid] = step
            _add_reference_effect(
                draft,
                event=event,
                payload_index=reference_payload_index,
                step=step,
                context_uid=timeline.context_uid,
                context_name=timeline.context_name,
            )
            reference_payload_index += 1

    entries_by_uid = {
        entry.get("uid"): entry
        for entry in entries
        if isinstance(entry.get("uid"), str)
    }
    for checkpoint in timeline.checkpoints:
        entry = entries_by_uid.get(checkpoint.uid)
        if entry is None:
            continue
        snapshot = entry.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        state = timeline.state(checkpoint.state_index)
        state_anchor = f"history-state:{state.index}:{state.record_digest}"
        _add_relationship_state(
            draft,
            record=snapshot,
            owner_context_uid=timeline.context_uid,
            owner_context_name=timeline.context_name,
            state_anchor=state_anchor,
            operation_step=steps_by_checkpoint.get(checkpoint.uid),
        )
    if current_record is not None:
        current_state = next(
            (state for state in reversed(timeline.states) if state.current),
            timeline.states[-1],
        )
        state_anchor = (
            f"history-state:{current_state.index}:{current_state.record_digest}"
        )
        _add_relationship_state(
            draft,
            record=current_record,
            owner_context_uid=timeline.context_uid,
            owner_context_name=timeline.context_name,
            state_anchor=state_anchor,
            operation_step=steps_by_checkpoint.get(current_state.checkpoint_uid),
        )

    operations = tuple(
        HistoryOperation(
            node_id=node_id,
            operation_uid=operation.operation_uid,
            checkpoint_uids=tuple(operation.checkpoint_uids),
            context_uids=tuple(operation.context_uids),
            sequence=operation.sequence,
        )
        for node_id, operation in sorted(
            draft.operations.items(),
            key=lambda item: (item[1].sequence, item[0]),
        )
    )
    steps = tuple(
        sorted(draft.steps.values(), key=lambda step: (step.sequence, step.node_id))
    )
    current_state = next(
        (state for state in reversed(timeline.states) if state.current),
        timeline.states[-1],
    )
    lineage = HistoryGraph(
        root_context_uid=timeline.context_uid,
        root_context_name=timeline.context_name,
        context_step_ids=context_step_ids,
        current_context_occurrence_id=_context_occurrence_id(
            timeline.context_uid,
            f"history-state:{current_state.index}:{current_state.record_digest}",
        ),
        operations=operations,
        steps=steps,
        occurrences=tuple(draft.occurrences.values()),
        effects=tuple(draft.effects),
        relations=tuple(draft.relations.values()),
        context_warnings=timeline.warnings,
        memory_warnings=tuple(memory_warnings),
        warnings=tuple(
            dict.fromkeys((*timeline.warnings, *tuple(memory_warnings)))
        ),
    )
    return HistoryGraphAssembly(
        graph=lineage,
        timeline=timeline,
        memory_events=events,
        memory_frames=frames,
        reference_evidence=references,
    )


def reconstruct_history_graph(
    store: HistoryEvidenceSource,
    context: Context,
) -> HistoryGraphAssembly:
    """Read verified retained evidence once into History's shared normal form."""

    timeline = build_history(store, context.name)
    events, warnings, frames = derive_memory_history_events(store, context)
    entries = _checkpoint_entries(store, context.name)
    references: list[HistoryReferenceEvidence] = []
    for candidate in collect_reference_candidates(store, context):
        reference_events, current = reference_occurrence_events(
            store,
            context,
            candidate.state.uid,
        )
        references.append(
            HistoryReferenceEvidence(
                candidate=candidate,
                events=reference_events,
                current=current,
            )
        )
    return reconstruct_history_graph_from_evidence(
        timeline=timeline,
        memory_events=events,
        memory_frames=frames,
        retained_entries=entries,
        current_record=context.to_dict(),
        memory_warnings=warnings,
        reference_evidence=tuple(references),
    )


__all__ = [
    "HistoryGraphAssembly",
    "HistoryReferenceEvidence",
    "reconstruct_history_graph",
    "reconstruct_history_graph_from_evidence",
]
