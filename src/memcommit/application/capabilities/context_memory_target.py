"""Project a multi-owner Context target into one reversible Memory frame."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
import uuid

from memcommit.models.context import Context
from memcommit.models.memory import Memory


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
    """Loaded target Contexts and their stable analysis-to-owner identities."""

    _contexts: tuple[Context, ...] = field(repr=False)
    origins: tuple[ContextMemoryOrigin, ...]
    analysis_context_uid: str

    def __post_init__(self):
        object.__setattr__(self, "_contexts", deepcopy(self._contexts))
        if len({item.analysis_uid for item in self.origins}) != len(self.origins):
            raise ValueError("Analysis Memory identities must be unique.")
        owners = {owner.uid: owner.name for owner in self._contexts}
        for item in self.origins:
            if owners.get(
                item.context_uid
            ) != item.context_name or item.analysis_uid != _analysis_memory_uid(
                self._contexts[0].uid, item.context_uid, item.memory_uid
            ):
                raise ValueError("Memory origin is outside its frozen Context target.")

    @property
    def contexts(self) -> tuple[Context, ...]:
        """Return owner copies so provider/preview work cannot alter the target."""
        return deepcopy(self._contexts)

    @classmethod
    def from_contexts(cls, contexts: tuple[Context, ...]):
        root_context = contexts[0]
        origins = tuple(
            ContextMemoryOrigin(
                _analysis_memory_uid(root_context.uid, owner.uid, memory.uid),
                owner.uid,
                owner.name,
                memory.uid,
            )
            for owner in contexts
            for memory in owner.iter_memories()
            if isinstance(memory, Memory)
        )
        identity = ":".join(sorted(owner.uid for owner in contexts))
        return cls(
            contexts,
            origins,
            str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"memcommit:scope-context:{root_context.uid}:{identity}",
                )
            ),
        )

    def analysis_context(self) -> Context:
        context = Context(uid=self.analysis_context_uid, name=self._contexts[0].name)
        by_identity = {
            (item.context_uid, item.memory_uid): item for item in self.origins
        }
        for owner in self._contexts:
            for memory in owner.iter_memories():
                if isinstance(memory, Memory):
                    origin = by_identity[owner.uid, memory.uid]
                    context.add(Memory(origin.analysis_uid, memory.content))
        return context

    def contexts_from_analysis(
        self, context: Context, extra_origins=()
    ) -> tuple[Context, ...]:
        if (
            context.uid != self.analysis_context_uid
            or context.name != self._contexts[0].name
        ):
            raise ValueError("Analysis result belongs to a different Context target.")
        origins = {item.analysis_uid: item for item in (*self.origins, *extra_origins)}
        contexts = deepcopy(self._contexts)
        owners = {owner.uid: owner for owner in contexts}
        for owner in owners.values():
            for memory in tuple(owner.iter_memories()):
                if isinstance(memory, Memory):
                    owner.remove(memory.uid)
        for memory in context.iter_memories():
            if not isinstance(memory, Memory) or memory.uid not in origins:
                raise ValueError("Analysis result has no original Memory placement.")
            origin = origins[memory.uid]
            owner = owners.get(origin.context_uid)
            if owner is None or owner.name != origin.context_name:
                raise ValueError("Analysis result names an unavailable owner.")
            owner.add(Memory(origin.memory_uid, memory.content))
        return contexts

    def with_analysis(self, context: Context, extra_origins=()):
        merged = {item.analysis_uid: item for item in (*self.origins, *extra_origins)}
        return ContextMemoryTarget(
            self.contexts_from_analysis(context, extra_origins),
            tuple(merged.values()),
            self.analysis_context_uid,
        )

    def project_update_plan(self, plan):
        """Keep the exact LLM-selected placement while calculating a flat result."""
        from memcommit.application.operations.update.model import AddOperation

        origins = {(item.context_uid, item.memory_uid): item for item in self.origins}
        additions = []
        operations = []
        owners = {owner.uid: owner.name for owner in self._contexts}
        for operation in plan.operations:
            key = operation.owner_context_uid, operation.memory_uid
            if owners.get(operation.owner_context_uid) != operation.owner_context_name:
                raise ValueError("Update selected an owner outside the Context target.")
            origin = origins.get(key)
            if origin is None:
                if not isinstance(operation, AddOperation):
                    raise ValueError("Update changed an unknown Memory.")
                origin = ContextMemoryOrigin(
                    _analysis_memory_uid(self._contexts[0].uid, *key),
                    operation.owner_context_uid,
                    operation.owner_context_name,
                    operation.memory_uid,
                )
                additions.append(origin)
            operations.append(
                replace(
                    operation,
                    owner_context_uid=self.analysis_context_uid,
                    owner_context_name=self._contexts[0].name,
                    memory_uid=origin.analysis_uid,
                )
            )
        return replace(
            plan,
            target_uid=self.analysis_context_uid,
            target_name=self._contexts[0].name,
            operations=tuple(operations),
        ), tuple(additions)

    def owner_update_plan(self, plan):
        origins = {item.analysis_uid: item for item in self.origins}
        operations = []
        for operation in plan.operations:
            if (
                operation.owner_context_uid != self.analysis_context_uid
                or operation.owner_context_name != self._contexts[0].name
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
            target_uid=self._contexts[0].uid,
            target_name=self._contexts[0].name,
            operations=tuple(operations),
        )


def plan_context_memory_update(
    memory_target, source, analysis_context, provider_factory, **options
):
    """Use ordinary multi-owner Update planning, then project its exact effects."""
    from memcommit.application.operations.update.model import plan_update

    if memory_target is None:
        return plan_update(
            (source,), (analysis_context,), provider_factory, **options
        ), ()
    contexts = memory_target.contexts_from_analysis(analysis_context)
    plan = plan_update(
        (source,),
        contexts,
        provider_factory,
        target_include_descendants=True,
        **options,
    )
    return memory_target.project_update_plan(plan)
