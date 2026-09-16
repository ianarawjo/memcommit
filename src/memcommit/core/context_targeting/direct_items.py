"""Resolve direct items inside one caller-supplied Context; no Store lookup."""

from __future__ import annotations

from memcommit.core.context import Context, Information, Memory, QueryContextRef


def resolve_direct_item(ctx: Context, selector: str) -> Information:
    """
    Resolve one direct child of *ctx* by UID prefix or embedded-context name.

    Atomic memories currently have no name, so they can only be selected by
    UID (or an unambiguous UID prefix). Embedded contexts can additionally be
    selected by their exact name. Raises KeyError if nothing matches and
    ValueError if the selector is ambiguous.
    """
    matches = [
        info
        for uid, info in ctx.iter_entries()
        if uid.startswith(selector)
        or (isinstance(info, (Context, QueryContextRef)) and info.name == selector)
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

    # Resolve the complete direct UID namespace before checking its type;
    # filtering out references first could hide an ambiguous selector.
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
