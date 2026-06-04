"""
    Pure in-memory operations on Context objects.
    No disk I/O here — callers persist via MemoryStore.save(ctx) when needed.

    These functions form the public Python API for memcommit:
        import memcommit.ops as ops
        mem = ops.add(ctx, "some information")
        ops.embed(child_ctx, parent_ctx)
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from memcommit.context import Context, Information, Memory

if TYPE_CHECKING:
    pass


def init(name: str) -> Context:
    """Create a new, empty Context. Does not persist — caller must store.save(ctx)."""
    return Context(uid=str(uuid.uuid4()), name=name)


def add(ctx: Context, content: str) -> Memory:
    """Add a new Memory to ctx. Returns the created Memory."""
    result = ctx.add(content)
    assert isinstance(result, Memory)
    return result


def remove(ctx: Context, uid: str) -> Information:
    """
    Remove an item from ctx by uid or unambiguous prefix.
    Returns the removed item. Raises KeyError if not found, ValueError if ambiguous.
    """
    matches = [k for k in ctx.memories if k.startswith(uid)]
    if not matches:
        raise KeyError(f"No item with uid starting with '{uid}'.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous prefix '{uid}' matches {len(matches)} items: "
            + ", ".join(m[:8] for m in matches)
        )
    full_uid = matches[0]
    item = ctx.memories[full_uid]
    ctx.remove(full_uid)
    return item


def embed(child: Context, parent: Context) -> None:
    """
    Embed child inside parent (as a live reference).
    Raises ValueError if already embedded or if child and parent are the same.
    """
    if child.uid == parent.uid:
        raise ValueError("Cannot embed a context into itself.")
    for info in parent.memories.values():
        if isinstance(info, Context) and info.name == child.name:
            raise ValueError(f"'{child.name}' is already embedded in '{parent.name}'.")
    parent.add(child)


def forget(ctx: Context, query: str) -> list[Information]:
    """[stub] Find and remove memories matching a natural-language description."""
    raise NotImplementedError("'forget' is not yet implemented.")


def find(ctx: Context, query: str) -> list[Information]:
    """[stub] Find memories matching a natural-language query."""
    raise NotImplementedError("'find' is not yet implemented.")
