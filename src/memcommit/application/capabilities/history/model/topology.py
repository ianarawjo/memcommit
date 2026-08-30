"""Canonical operation, occurrence, effect, and relation History topology.

The topology is deliberately mechanical.  Operation identity comes from
verified receipt identifiers or checkpoint identity, occurrence identity comes
from durable Context/Memory coordinates plus a state anchor, and connectivity
comes only from typed relations.  Human-readable command descriptions are
retained on steps for presentation but are never parsed to infer lineage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Literal, Mapping


HistoryOccurrenceKind = Literal[
    "CONTEXT",
    "MEMORY",
    "MEMORY_REFERENCE",
]
HistoryRelationKind = Literal[
    "INPUT",
    "OUTPUT",
    "CONTAINS",
    "CONTINUES_AS",
    "DERIVED_FROM",
    "EMBEDS",
    "REFERENCES",
]
HistoryEffectChannel = Literal["CONTEXT", "MEMORY", "REFERENCE"]
HistoryEvidence = Literal["RECORDED", "RECONSTRUCTED", "INFERRED", "UNRECORDED"]
HistoryEffectKind = Literal[
    "CREATED",
    "EDITED",
    "REMOVED",
    "RESTORED",
    "SPLIT",
    "ABSORBED",
    "MERGED_IN",
    "TRANSLATED",
    "ATOMIZE_KEEP",
    "ATOMIZE_PRESERVED",
    "MELDED",
    "BRANCHED",
    "REORDERED",
    "HISTORY_GAP",
    "RETARGETED",
    "TARGET_RENAMED",
    "EARLIEST_RETAINED",
]


@dataclass(frozen=True, slots=True)
class HistoryOperation:
    """One command unit, possibly evidenced by several checkpoints."""

    node_id: str
    operation_uid: str | None
    checkpoint_uids: tuple[str, ...]
    context_uids: tuple[str, ...]
    sequence: int


@dataclass(frozen=True, slots=True)
class HistoryStep:
    """One exact checkpoint/current-state occurrence of an operation."""

    node_id: str
    operation_node_id: str
    context_uid: str
    context_name: str
    checkpoint_uid: str | None
    timestamp: str | None
    command: str
    description: str
    evidence: HistoryEvidence
    sequence: int


@dataclass(frozen=True, slots=True)
class HistoryOccurrence:
    """One Context, Memory, or relationship occurrence at one state anchor."""

    node_id: str
    kind: HistoryOccurrenceKind
    context_uid: str
    context_name: str
    subject_uid: str
    state_anchor: str
    content: str | None = None
    content_digest: str | None = None
    position: int | None = None
    selectable: bool = False


@dataclass(frozen=True, slots=True)
class HistoryEffect:
    """One typed state change attached to an exact operation step."""

    effect_id: str
    channel: HistoryEffectChannel
    operation_node_id: str
    operation_step_id: str
    kind: HistoryEffectKind
    evidence: HistoryEvidence
    before_occurrence_ids: tuple[str, ...]
    after_occurrence_ids: tuple[str, ...]
    payload_index: int | None = None


@dataclass(frozen=True, slots=True)
class HistoryRelation:
    """One explicit topology edge; labels, not prose, define its meaning."""

    relation_id: str
    kind: HistoryRelationKind
    source_node_id: str
    target_node_id: str
    operation_node_id: str | None = None
    operation_step_id: str | None = None
    effect_id: str | None = None


_LINEAGE_EFFECT_KINDS = frozenset(
    {"SPLIT", "ABSORBED", "TRANSLATED", "BRANCHED", "MERGED_IN"}
)
_COUNT_COMPONENT_EFFECT_KINDS = frozenset(
    {"SPLIT", "ABSORBED", "TRANSLATED", "BRANCHED"}
)


@dataclass(frozen=True, slots=True)
class HistoryGraph:
    """A deterministic operation/occurrence graph for one History assembly."""

    root_context_uid: str
    root_context_name: str
    context_step_ids: tuple[str, ...]
    current_context_occurrence_id: str
    operations: tuple[HistoryOperation, ...]
    steps: tuple[HistoryStep, ...]
    occurrences: tuple[HistoryOccurrence, ...]
    effects: tuple[HistoryEffect, ...]
    relations: tuple[HistoryRelation, ...]
    context_warnings: tuple[str, ...] = ()
    memory_warnings: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    _occurrences_by_id: Mapping[str, HistoryOccurrence] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _steps_by_id: Mapping[str, HistoryStep] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        operation_ids = {node.node_id for node in self.operations}
        step_ids = {step.node_id for step in self.steps}
        occurrence_ids = {node.node_id for node in self.occurrences}
        effect_ids = {effect.effect_id for effect in self.effects}
        relation_ids = {relation.relation_id for relation in self.relations}
        if len(operation_ids) != len(self.operations):
            raise ValueError("History operation node identities must be unique.")
        if len(step_ids) != len(self.steps):
            raise ValueError("History operation step identities must be unique.")
        if len(occurrence_ids) != len(self.occurrences):
            raise ValueError("History occurrence node identities must be unique.")
        if len(effect_ids) != len(self.effects):
            raise ValueError("History effect identities must be unique.")
        if len(relation_ids) != len(self.relations):
            raise ValueError("History relation identities must be unique.")
        object.__setattr__(
            self,
            "_occurrences_by_id",
            MappingProxyType({node.node_id: node for node in self.occurrences}),
        )
        object.__setattr__(
            self,
            "_steps_by_id",
            MappingProxyType({step.node_id: step for step in self.steps}),
        )
        if len(set(self.context_step_ids)) != len(self.context_step_ids):
            raise ValueError("History Context projection repeats an operation step.")
        if any(step_id not in step_ids for step_id in self.context_step_ids):
            raise ValueError("History Context projection refers to an unknown step.")
        if self.current_context_occurrence_id not in occurrence_ids:
            raise ValueError("History current Context occurrence is missing.")
        current_context = self.occurrence(self.current_context_occurrence_id)
        if (
            current_context.kind != "CONTEXT"
            or current_context.context_uid != self.root_context_uid
            or current_context.subject_uid != self.root_context_uid
        ):
            raise ValueError("History current occurrence does not match its root Context.")
        if any(step.operation_node_id not in operation_ids for step in self.steps):
            raise ValueError("History step refers to an unknown operation node.")
        if any(
            effect.operation_node_id not in operation_ids
            or effect.operation_step_id not in step_ids
            or any(
                occurrence_id not in occurrence_ids
                for occurrence_id in (
                    *effect.before_occurrence_ids,
                    *effect.after_occurrence_ids,
                )
            )
            for effect in self.effects
        ):
            raise ValueError("History effect refers to an unknown topology node.")
        all_node_ids = operation_ids | step_ids | occurrence_ids
        if any(
            relation.source_node_id not in all_node_ids
            or relation.target_node_id not in all_node_ids
            or (
                relation.operation_node_id is not None
                and relation.operation_node_id not in operation_ids
            )
            or (
                relation.operation_step_id is not None
                and relation.operation_step_id not in step_ids
            )
            or (
                relation.effect_id is not None
                and relation.effect_id not in effect_ids
            )
            for relation in self.relations
        ):
            raise ValueError("History relation refers to an unknown topology node.")

    def occurrence(self, node_id: str) -> HistoryOccurrence:
        try:
            return self._occurrences_by_id[node_id]
        except KeyError as error:
            raise KeyError(node_id) from error

    def step(self, node_id: str) -> HistoryStep:
        try:
            return self._steps_by_id[node_id]
        except KeyError as error:
            raise KeyError(node_id) from error

    def known_memory_uids(self) -> set[str]:
        """Return the exact direct/event Memory selector domain."""

        return {
            occurrence.subject_uid
            for occurrence in self.occurrences
            if occurrence.kind == "MEMORY" and occurrence.selectable
        }

    def resolve_memory_uid(self, selector: str) -> str:
        if not isinstance(selector, str) or not selector:
            raise ValueError("Memory selector must be non-empty.")
        matches = sorted(
            uid for uid in self.known_memory_uids() if uid.startswith(selector)
        )
        if not matches:
            raise KeyError(selector)
        if len(matches) > 1:
            raise LookupError(tuple(matches))
        return matches[0]

    def memory_component(self, selected_uid: str) -> set[str]:
        """Follow only typed lineage-producing effects from one Memory UID."""

        adjacency = self._memory_adjacency(_LINEAGE_EFFECT_KINDS)
        component = {selected_uid}
        pending = [selected_uid]
        while pending:
            uid = pending.pop()
            for neighbor in adjacency.get(uid, ()):
                if neighbor in component:
                    continue
                component.add(neighbor)
                pending.append(neighbor)
        return component

    def memory_event_indexes(self, component: set[str]) -> tuple[int, ...]:
        return tuple(
            effect.payload_index
            for effect in self.effects
            if effect.channel == "MEMORY"
            and effect.payload_index is not None
            and self._effect_memory_uids(effect) & component
        )

    def memory_operation_counts(
        self,
        selected_uids: Iterable[str],
    ) -> dict[str, int]:
        """Count distinct operation nodes using the historical picker rules."""

        candidates = tuple(dict.fromkeys(selected_uids))
        operations_by_uid: dict[str, set[str]] = {uid: set() for uid in candidates}
        for effect in self.effects:
            if effect.channel != "MEMORY" or effect.kind == "HISTORY_GAP":
                continue
            for uid in self._effect_memory_uids(effect):
                operations_by_uid.setdefault(uid, set()).add(
                    effect.operation_node_id
                )
        adjacency = self._memory_adjacency(_COUNT_COMPONENT_EFFECT_KINDS)
        counts: dict[str, int] = {}
        visited: set[str] = set()
        for selected_uid in candidates:
            if selected_uid in visited:
                continue
            component = {selected_uid}
            pending = [selected_uid]
            while pending:
                uid = pending.pop()
                for neighbor in adjacency.get(uid, ()):
                    if neighbor in component:
                        continue
                    component.add(neighbor)
                    pending.append(neighbor)
            visited.update(component)
            count = len(
                set().union(
                    *(operations_by_uid.get(uid, set()) for uid in component)
                )
            )
            for uid in component:
                if uid in operations_by_uid:
                    counts[uid] = count
        return counts

    def _effect_memory_uids(self, effect: HistoryEffect) -> set[str]:
        return {
            self.occurrence(node_id).subject_uid
            for node_id in (
                *effect.before_occurrence_ids,
                *effect.after_occurrence_ids,
            )
            if self.occurrence(node_id).kind == "MEMORY"
        }

    def _memory_adjacency(
        self,
        included_kinds: frozenset[str],
    ) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {}
        for effect in self.effects:
            if effect.channel != "MEMORY" or effect.kind not in included_kinds:
                continue
            before = {
                self.occurrence(node_id).subject_uid
                for node_id in effect.before_occurrence_ids
                if self.occurrence(node_id).kind == "MEMORY"
            }
            after = {
                self.occurrence(node_id).subject_uid
                for node_id in effect.after_occurrence_ids
                if self.occurrence(node_id).kind == "MEMORY"
            }
            for source in before:
                adjacency.setdefault(source, set()).update(after)
            for result in after:
                adjacency.setdefault(result, set()).update(before)
        return adjacency


__all__ = [
    "HistoryEffect",
    "HistoryEffectChannel",
    "HistoryEffectKind",
    "HistoryEvidence",
    "HistoryGraph",
    "HistoryOccurrenceKind",
    "HistoryOccurrence",
    "HistoryOperation",
    "HistoryStep",
    "HistoryRelation",
    "HistoryRelationKind",
]
