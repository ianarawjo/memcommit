"""
    Defines an abstract memory store, called a "context" in memcommit.
    Contexts store atomic chunks of information, called memories.

    At the basic level, a Context simply stores a set of memories
    and manages this set's updating and retrieval.
"""
from __future__ import annotations

from typing import Protocol, TypeAlias, runtime_checkable

@runtime_checkable
class Identifiable(Protocol):
    """
        Any object that has a unique identifier (uid) can be considered an Identifiable.
    """
    uid: str

class Memory(Identifiable):
    """
        Atomic chunk of information.
        Note that the format of the memory does not matter here; format is abstracted. 
    """

    def __init__(self, uid: str, content: str):
        self.uid = uid
        self.content = content

class Context(Identifiable):
    """
        Abstract memory store. 
        A Context is a collection of Memories or other Contexts.
    """

    def __init__(self, uid: str, name: str):
        self.uid = uid
        self.name = name
        self.memories: dict[str, Information] = dict()

    def add(self, memory: Information):
        """Add a memory to the context."""
        self.memories[memory.uid] = memory
    
    def remove(self, uid: str):
        """Remove a memory from the context by its uid."""
        if uid in self.memories:
            del self.memories[uid]
        else:
            raise KeyError(f"Memory with uid {uid} not found in context.")

    def get_all(self) -> dict[str, Information]:
        """Get all memories in the context."""
        return self.memories


# A piece of information in a context can be either a Memory or another Context (i.e., a nested context).
Information: TypeAlias = Memory | Context