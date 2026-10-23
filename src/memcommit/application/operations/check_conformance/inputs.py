"""Freeze complete Conformance evidence and recheck its live owners."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from memcommit.application.context_access.access import ContextAccess
from memcommit.application.operations.check_conformance.model import ConformanceError
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.persistence.store import MemoryStore, context_record_digest


class ConformanceInputError(ConformanceError):
    """Conformance evidence is unavailable or no longer matches its frozen value."""


@dataclass(frozen=True)
class ConformanceReadDependency:
    store: MemoryStore
    name: str
    uid: str
    digest: str | None
    memory_digest: tuple[str, str] | None = None
    access: ContextAccess | None = None


@dataclass(frozen=True)
class ConformanceInputs:
    root: Context
    memories: tuple[Memory, ...]
    dependencies: tuple[ConformanceReadDependency, ...]


def _memory_digest(memory: Memory) -> str:
    return hashlib.sha256(memory.content.encode("utf-8")).hexdigest()


def capture_conformance_dependency(
    store: MemoryStore,
    context: Context,
    *,
    access: ContextAccess | None = None,
    memory: Memory | None = None,
) -> ConformanceReadDependency:
    # A selected Rule Memory must not depend on unrelated owner content.
    return ConformanceReadDependency(
        store=store,
        name=context.name,
        uid=context.uid,
        digest=context_record_digest(context) if memory is None else None,
        memory_digest=(memory.uid, _memory_digest(memory))
        if memory is not None
        else None,
        access=access,
    )


def prepare_conformance_inputs(
    store: MemoryStore, name: str, *, loaded_context: Context | None = None
) -> ConformanceInputs:
    root = loaded_context if loaded_context is not None else store.load_direct(name)
    dependency = capture_conformance_dependency(store, root)
    return ConformanceInputs(root, tuple(root.iter_memories()), (dependency,))


def revalidate_conformance_inputs(
    dependencies: tuple[ConformanceReadDependency, ...],
    *,
    active_store: MemoryStore,
) -> None:
    for dependency in dependencies:
        reader = dependency.store
        try:
            current = reader.load_direct(dependency.name)
        except FileNotFoundError as error:
            raise ConformanceInputError(
                f"Context input {dependency.name!r} disappeared."
            ) from error
        if current.uid != dependency.uid:
            raise ConformanceInputError(
                f"Context input {dependency.name!r} changed identity."
            )
        if (
            dependency.digest is not None
            and context_record_digest(current) != dependency.digest
        ):
            raise ConformanceInputError(
                f"Context input {dependency.name!r} changed content."
            )
        if dependency.memory_digest is not None:
            uid, digest = dependency.memory_digest
            memory = current.memories.get(uid)
            if not isinstance(memory, Memory) or _memory_digest(memory) != digest:
                raise ConformanceInputError(
                    f"Memory input [{uid[:8]}] in {dependency.name!r} changed."
                )
