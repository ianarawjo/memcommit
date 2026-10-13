"""Project a multi-owner Context target into one reversible Memory frame."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
import uuid

from memcommit.core.context import Context, Memory
from .context_scope_loading import walk_context_owners


@dataclass(frozen=True, slots=True)
class ContextMemoryOrigin:
    analysis_uid: str
    context_uid: str
    context_name: str
    memory_uid: str


def _analysis_memory_uid(root_uid, owner_uid, memory_uid):
    # Owner identity distinguishes equal Memory UIDs in different Contexts.
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL, f"memcommit:scope:{root_uid}:{owner_uid}:{memory_uid}"
        )
    )


@dataclass(frozen=True)
class ContextMemoryTarget:
    """One loaded target graph and its stable analysis-to-owner identities."""

    _graph: Context = field(repr=False)
    origins: tuple[ContextMemoryOrigin, ...]
    analysis_context_uid: str

    def __post_init__(self):
        object.__setattr__(self, "_graph", deepcopy(self._graph))
        if len({item.analysis_uid for item in self.origins}) != len(self.origins):
            raise ValueError("Analysis Memory identities must be unique.")
        owners = {owner.uid: owner.name for owner in walk_context_owners(self._graph)}
        for item in self.origins:
            if owners.get(
                item.context_uid
            ) != item.context_name or item.analysis_uid != _analysis_memory_uid(
                self._graph.uid, item.context_uid, item.memory_uid
            ):
                raise ValueError("Memory origin is outside its frozen Context target.")

    @property
    def graph(self) -> Context:
        """Return an owner graph copy; provider/preview work cannot alter the target."""
        return deepcopy(self._graph)

    @classmethod
    def from_context(cls, graph: Context):
        owners = walk_context_owners(graph)
        origins = tuple(
            ContextMemoryOrigin(
                _analysis_memory_uid(graph.uid, owner.uid, memory.uid),
                owner.uid,
                owner.name,
                memory.uid,
            )
            for owner in owners
            for memory in owner.iter_items()
            if isinstance(memory, Memory)
        )
        identity = ":".join(sorted(owner.uid for owner in owners))
        return cls(
            graph,
            origins,
            str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"memcommit:scope-context:{graph.uid}:{identity}",
                )
            ),
        )

    def analysis_context(self) -> Context:
        context = Context(uid=self.analysis_context_uid, name=self._graph.name)
        by_identity = {
            (item.context_uid, item.memory_uid): item for item in self.origins
        }
        for owner in walk_context_owners(self._graph):
            for memory in owner.iter_items():
                if isinstance(memory, Memory):
                    origin = by_identity[owner.uid, memory.uid]
                    context.add(Memory(origin.analysis_uid, memory.content))
        return context

    def graph_from_analysis(self, context: Context, extra_origins=()) -> Context:
        if context.uid != self.analysis_context_uid or context.name != self._graph.name:
            raise ValueError("Analysis result belongs to a different Context target.")
        origins = {item.analysis_uid: item for item in (*self.origins, *extra_origins)}
        graph = deepcopy(self._graph)
        owners = {owner.uid: owner for owner in walk_context_owners(graph)}
        for owner in owners.values():
            for memory in tuple(owner.iter_items()):
                if isinstance(memory, Memory):
                    owner.remove(memory.uid)
        for memory in context.iter_items():
            if not isinstance(memory, Memory) or memory.uid not in origins:
                raise ValueError("Analysis result has no original Memory placement.")
            origin = origins[memory.uid]
            owner = owners.get(origin.context_uid)
            if owner is None or owner.name != origin.context_name:
                raise ValueError("Analysis result names an unavailable owner.")
            owner.add(Memory(origin.memory_uid, memory.content))
        return graph

    def with_analysis(self, context: Context, extra_origins=()):
        merged = {item.analysis_uid: item for item in (*self.origins, *extra_origins)}
        return ContextMemoryTarget(
            self.graph_from_analysis(context, extra_origins),
            tuple(merged.values()),
            self.analysis_context_uid,
        )

    def project_update_plan(self, plan):
        """Keep the exact LLM-selected placement while calculating a flat result."""
        from memcommit.application.operations.update.model import AddOperation

        origins = {(item.context_uid, item.memory_uid): item for item in self.origins}
        additions = []
        operations = []
        owners = {owner.uid: owner.name for owner in walk_context_owners(self._graph)}
        for operation in plan.operations:
            key = operation.owner_context_uid, operation.memory_uid
            if owners.get(operation.owner_context_uid) != operation.owner_context_name:
                raise ValueError("Update selected an owner outside the Context target.")
            origin = origins.get(key)
            if origin is None:
                if not isinstance(operation, AddOperation):
                    raise ValueError("Update changed an unknown Memory.")
                origin = ContextMemoryOrigin(
                    _analysis_memory_uid(self._graph.uid, *key),
                    operation.owner_context_uid,
                    operation.owner_context_name,
                    operation.memory_uid,
                )
                additions.append(origin)
            operations.append(
                replace(
                    operation,
                    owner_context_uid=self.analysis_context_uid,
                    owner_context_name=self._graph.name,
                    memory_uid=origin.analysis_uid,
                )
            )
        return replace(
            plan,
            target_uid=self.analysis_context_uid,
            target_name=self._graph.name,
            operations=tuple(operations),
        ), tuple(additions)

    def owner_update_plan(self, plan):
        origins = {item.analysis_uid: item for item in self.origins}
        operations = []
        for operation in plan.operations:
            if (
                operation.owner_context_uid != self.analysis_context_uid
                or operation.owner_context_name != self._graph.name
            ):
                raise ValueError("Update plan belongs to another analysis target.")
            origin = origins.get(operation.memory_uid)
            if origin is None:
                raise ValueError("Update plan has no reviewed Memory placement.")
            operations.append(
                replace(
                    operation,
                    owner_context_uid=origin.context_uid,
                    owner_context_name=origin.context_name,
                    memory_uid=origin.memory_uid,
                )
            )
        return replace(
            plan,
            target_uid=self._graph.uid,
            target_name=self._graph.name,
            operations=tuple(operations),
        )


def plan_context_memory_update(
    memory_target, source, analysis_context, provider_factory, **options
):
    """Use ordinary multi-owner Update planning, then project its exact effects."""
    from memcommit.application.operations.update.model import plan_update

    if memory_target is None:
        return plan_update(source, analysis_context, provider_factory, **options), ()
    graph = memory_target.graph_from_analysis(analysis_context)
    plan = plan_update(
        source, graph, provider_factory, target_include_descendants=True, **options
    )
    return memory_target.project_update_plan(plan)
