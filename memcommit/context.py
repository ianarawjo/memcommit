"""
    Defines an abstract memory store, called a "context" in memcommit.
    Contexts store atomic chunks of information, called memories.

    At the basic level, a Context simply stores a set of memories
    and manages this set's updating and retrieval.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, TypeAlias, runtime_checkable


@runtime_checkable
class Identifiable(Protocol):
    uid: str


class Memory:
    """Atomic chunk of information."""

    def __init__(self, uid: str, content: str):
        self.uid = uid
        self.content = content


class Context:
    """
    Abstract memory store.
    A Context is a collection of Memories or other Contexts (nested by reference).
    """

    def __init__(self, uid: str, name: str):
        self.uid = uid
        self.name = name
        self.memories: dict[str, Information] = {}

    def add(self, info: Information) -> None:
        self.memories[info.uid] = info

    def remove(self, uid: str) -> None:
        if uid not in self.memories:
            raise KeyError(f"No item with uid '{uid}' in context '{self.name}'.")
        del self.memories[uid]

    def get_all(self) -> dict[str, Information]:
        return self.memories


# A piece of information in a context is either an atomic Memory or a nested Context.
Information: TypeAlias = Memory | Context


@dataclass
class Checkpoint:
    """Point-in-time snapshot of a context's direct state."""
    uid: str
    message: str
    timestamp: datetime
    snapshot: dict[str, Any]  # serialized memories (context refs stored by ref, not inline)