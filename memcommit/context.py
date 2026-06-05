"""
    Defines an abstract memory store, called a "context" in memcommit.
    Contexts store atomic chunks of information, called memories.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Protocol, TypeAlias, runtime_checkable


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


class Context:
    """
    Abstract memory store.
    A Context is a collection of Memories or other Contexts (nested by reference).
    """

    def __init__(self, uid: str, name: str):
        self.uid = uid
        self.name = name
        self.memories: dict[str, Information] = {}

    def add(self, info: str | Information) -> Information:
        """
        Add information to this context.
        If info is a plain string, it is wrapped in a new Memory automatically.
        Returns the added Information (useful when a string was auto-promoted).
        """
        if isinstance(info, str):
            info = Memory(uid=str(uuid.uuid4()), content=info)
        self.memories[info.uid] = info
        return info

    def remove(self, uid: str) -> None:
        if uid not in self.memories:
            raise KeyError(f"No item with uid '{uid}' in context '{self.name}'.")
        del self.memories[uid]

    def get_all(self) -> dict[str, Information]:
        return self.memories

    def replace(self, memory: Memory) -> None:
        """Replace an existing Memory in-place by uid. Raises if uid is absent or is a Context."""
        if memory.uid not in self.memories:
            raise KeyError(f"No memory with uid '{memory.uid}' in context '{self.name}'.")
        if not isinstance(self.memories[memory.uid], Memory):
            raise TypeError(f"'{memory.uid}' is an embedded context, not a Memory.")
        self.memories[memory.uid] = memory

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict. Embedded contexts are stored as refs, not inline."""
        memories: dict[str, Any] = {}
        for uid, info in self.memories.items():
            if isinstance(info, Memory):
                memories[uid] = info.to_dict()
            elif isinstance(info, Context):
                memories[uid] = {"type": "context_ref", "uid": info.uid, "name": info.name}
        return {"uid": self.uid, "name": self.name, "memories": memories}

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        loader: Callable[[str], Context | None] | None = None,
    ) -> Context:
        """
        Deserialize from a dict produced by to_dict().
        loader(name) is called to resolve context_refs; if absent or returning None,
        the ref is silently skipped.
        """
        ctx = cls(uid=data["uid"], name=data["name"])
        for item in data["memories"].values():
            if item["type"] == "memory":
                ctx.add(Memory.from_dict(item))
            elif item["type"] == "context_ref" and loader is not None:
                nested = loader(item["name"])
                if nested is not None:
                    ctx.add(nested)
        return ctx


# A piece of information in a context is either an atomic Memory or a nested Context.
Information: TypeAlias = Memory | Context


@dataclass
class Checkpoint:
    """Point-in-time snapshot of a context's direct state."""
    uid: str
    message: str
    timestamp: datetime
    snapshot: dict[str, Any]  # result of ctx.to_dict() at checkpoint time
