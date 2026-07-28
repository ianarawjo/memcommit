"""
    Defines an abstract memory store, called a "context" in memcommit.
    Contexts store atomic chunks of information, called memories.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator, Optional, Protocol, TypeAlias, runtime_checkable


@runtime_checkable
class Identifiable(Protocol):
    uid: str


class Memory:
    """Atomic chunk of information."""

    def __init__(self, uid: str, content: str):
        self.uid = uid
        self.content = content

    def to_dict(self) -> dict[str, Any]:
        return {"type": "memory", "uid": self.uid, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        return cls(uid=data["uid"], content=data["content"])


class MemoryRef:
    """Read-only reference to one directly owned Memory in another Context."""

    def __init__(
        self,
        uid: str,
        target_context_uid: str,
        target_context_name: str,
        target_memory_uid: str,
        target: Memory | None = None,
    ):
        self.uid = uid
        self.target_context_uid = target_context_uid
        self.target_context_name = target_context_name
        self.target_memory_uid = target_memory_uid
        # Keep a detached view so mutating ref.target cannot write through to
        # a source Context object. Parent serialization ignores this content.
        self.target = (
            Memory(uid=target.uid, content=target.content)
            if target is not None
            else None
        )

    @property
    def is_resolved(self) -> bool:
        return self.target is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the pointer only; target content is intentionally omitted."""
        return {
            "type": "memory_ref",
            "uid": self.uid,
            "target_context": {
                "uid": self.target_context_uid,
                "name": self.target_context_name,
            },
            "target_memory_uid": self.target_memory_uid,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        target: Memory | None = None,
    ) -> MemoryRef:
        target_context = data["target_context"]
        return cls(
            uid=data["uid"],
            target_context_uid=target_context["uid"],
            target_context_name=target_context["name"],
            target_memory_uid=data["target_memory_uid"],
            target=target,
        )

    def copy(self) -> MemoryRef:
        """Copy the reference record while keeping the same target identity."""
        return MemoryRef(
            uid=self.uid,
            target_context_uid=self.target_context_uid,
            target_context_name=self.target_context_name,
            target_memory_uid=self.target_memory_uid,
            target=self.target,
        )


class QueryContextRef:
    """Opaque reference to a Context that can be accessed only through queries."""

    def __init__(
        self,
        uid: str,
        name: str,
        target_source_uid: str,
        provider: str,
    ):
        self.uid = uid
        self.name = name
        self.target_source_uid = target_source_uid
        self.provider = provider

    def to_dict(self) -> dict[str, Any]:
        """Serialize query routing metadata without serializing source content."""
        return {
            "type": "query_context_ref",
            "uid": self.uid,
            "name": self.name,
            "target_source_uid": self.target_source_uid,
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryContextRef:
        return cls(
            uid=data["uid"],
            name=data["name"],
            target_source_uid=data["target_source_uid"],
            provider=data["provider"],
        )

    def copy(self) -> QueryContextRef:
        """Copy the pointer record while preserving its source identity."""
        return QueryContextRef(
            uid=self.uid,
            name=self.name,
            target_source_uid=self.target_source_uid,
            provider=self.provider,
        )


class Context:
    """
    Abstract memory store.
    A Context is an ordered collection of Memories, MemoryRefs,
    QueryContextRefs, or other Contexts (nested by reference).
    """

    def __init__(self, uid: str, name: str):
        self.uid = uid
        self.name = name
        self.memories: dict[str, Information] = {}
        self.order: list[str] = []

    def ordered_uids(self) -> list[str]:
        """
        Return the canonical direct-item order.

        Invalid/duplicate entries are ignored and any items missing from an
        externally modified order list are appended in dict insertion order.
        """
        result: list[str] = []
        seen: set[str] = set()
        for uid in [*self.order, *self.memories.keys()]:
            if uid in self.memories and uid not in seen:
                result.append(uid)
                seen.add(uid)
        return result

    def iter_entries(self) -> Iterator[tuple[str, Information]]:
        """Iterate direct items in explicit Context order."""
        for uid in self.ordered_uids():
            yield uid, self.memories[uid]

    def iter_items(self) -> Iterator[Information]:
        """Iterate direct items in explicit Context order."""
        for _, info in self.iter_entries():
            yield info

    def add(
        self,
        info: str | Information,
        position: int | None = None,
    ) -> Information:
        """
        Add information to this context.
        If info is a plain string, it is wrapped in a new Memory automatically.
        New items are appended unless position is supplied. Replacing an
        existing uid keeps its current position.
        Returns the added Information (useful when a string was auto-promoted).
        """
        if isinstance(info, str):
            info = Memory(uid=str(uuid.uuid4()), content=info)

        current_order = self.ordered_uids()
        already_present = info.uid in self.memories
        self.memories[info.uid] = info

        if already_present:
            self.order = current_order
        elif position is None:
            self.order = [*current_order, info.uid]
        else:
            index = max(0, min(position, len(current_order)))
            self.order = [*current_order[:index], info.uid, *current_order[index:]]
        return info

    def remove(self, uid: str) -> None:
        if uid not in self.memories:
            raise KeyError(f"No item with uid '{uid}' in context '{self.name}'.")
        del self.memories[uid]
        self.order = [item_uid for item_uid in self.order if item_uid != uid]

    def clear(self) -> None:
        """Remove all direct items and their ordering metadata."""
        self.memories.clear()
        self.order.clear()

    def get_all(self) -> dict[str, Information]:
        return self.memories

    def replace(self, memory: Memory) -> None:
        """Replace a directly owned Memory in-place, preserving its position."""
        if memory.uid not in self.memories:
            raise KeyError(f"No memory with uid '{memory.uid}' in context '{self.name}'.")
        if not isinstance(self.memories[memory.uid], Memory):
            raise TypeError(f"'{memory.uid}' is not a directly owned Memory.")
        self.memories[memory.uid] = memory

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict. References are stored without target contents."""
        memories: dict[str, Any] = {}
        order: list[str] = []
        for uid, info in self.iter_entries():
            if isinstance(info, Memory):
                memories[uid] = info.to_dict()
                order.append(uid)
            elif isinstance(info, MemoryRef):
                memories[uid] = info.to_dict()
                order.append(uid)
            elif isinstance(info, QueryContextRef):
                memories[uid] = info.to_dict()
                order.append(uid)
            elif isinstance(info, Context):
                memories[uid] = {"type": "context_ref", "uid": info.uid, "name": info.name}
                order.append(uid)
        return {
            "uid": self.uid,
            "name": self.name,
            "memories": memories,
            "order": order,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        loader: Callable[[str], Context | None] | None = None,
        memory_loader: Callable[[str, str, str], Memory | None] | None = None,
    ) -> Context:
        """
        Deserialize from a dict produced by to_dict().
        loader(name) is called to resolve context_refs; if absent or returning None,
        the ref is silently skipped.

        memory_loader(context_name, context_uid, memory_uid) resolves memory_refs.
        A memory_ref is retained with target=None when it cannot be resolved.
        Files without an explicit order use their memories key order.
        """
        ctx = cls(uid=data["uid"], name=data["name"])
        serialized = data.get("memories", {})
        requested_order = data.get("order")
        keys: list[str] = []
        seen: set[str] = set()

        if isinstance(requested_order, list):
            for uid in requested_order:
                if isinstance(uid, str) and uid in serialized and uid not in seen:
                    keys.append(uid)
                    seen.add(uid)
        for uid in serialized:
            if uid not in seen:
                keys.append(uid)
                seen.add(uid)

        for uid in keys:
            item = serialized[uid]
            if item["type"] == "memory":
                ctx.add(Memory.from_dict(item))
            elif item["type"] == "memory_ref":
                target_context = item["target_context"]
                target = None
                if memory_loader is not None:
                    target = memory_loader(
                        target_context["name"],
                        target_context["uid"],
                        item["target_memory_uid"],
                    )
                ctx.add(MemoryRef.from_dict(item, target=target))
            elif item["type"] == "query_context_ref":
                ctx.add(QueryContextRef.from_dict(item))
            elif item["type"] == "context_ref" and loader is not None:
                nested = loader(item["name"])
                if nested is not None:
                    ctx.add(nested)
        return ctx


# A direct item is an atomic Memory, a read-only MemoryRef, an opaque
# QueryContextRef, or a nested Context.
Information: TypeAlias = Memory | MemoryRef | QueryContextRef | Context


@dataclass
class AutoCheckpoint:
    """Passed to store.save() to trigger an automatic post-operation checkpoint."""
    command: str
    args: dict[str, Any]
    description: str


@dataclass
class Checkpoint:
    """Point-in-time snapshot of a context's direct state."""
    uid: str
    message: str
    timestamp: datetime
    snapshot: dict[str, Any]  # result of ctx.to_dict() at checkpoint time
    command: Optional[str] = None
    args: Optional[dict[str, Any]] = None
    description: Optional[str] = None
    auto: bool = False
