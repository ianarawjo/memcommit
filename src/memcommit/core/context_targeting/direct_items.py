"""Resolve direct items inside one caller-supplied Context; no Store lookup."""

from __future__ import annotations

from memcommit.models.context import Context
from memcommit.models.memory import Memory


def resolve_direct_item(ctx: Context, selector: str) -> Memory:
    """
    Resolve one directly owned Memory by its unique UID prefix.

    Memories are selected by UID or an unambiguous UID prefix.
    Raises KeyError if nothing matches and
    ValueError if the selector is ambiguous.
    """
    matches = [
        memory for memory in ctx.iter_memories() if memory.uid.startswith(selector)
    ]
    if not matches:
        raise KeyError(f"No direct item matching '{selector}' in context '{ctx.name}'.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous selector '{selector}' matches {len(matches)} items: "
            + ", ".join(item.uid[:8] for item in matches)
        )
    return matches[0]


def resolve_direct_memory(ctx: Context, selector: str) -> Memory:
    """Resolve one ordinary directly owned Memory with Edit's prefix grammar."""

    matches = [uid for uid in ctx.memories if uid.startswith(selector)]
    if not matches:
        raise KeyError(f"No item with uid starting with '{selector}'.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous prefix '{selector}' matches {len(matches)} items: "
            + ", ".join(uid[:8] for uid in matches)
        )

    item = ctx.memories[matches[0]]
    if not isinstance(item, Memory):
        raise TypeError(
            f"'{selector}' is not a Memory directly owned by this Context — "
            "cannot edit."
        )
    return item
