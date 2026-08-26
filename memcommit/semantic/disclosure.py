"""Fail-closed authority preflight for provider-facing Context graphs.

Readable live Grant relationships may be traversed for local inspection, but a
local containing Context does not own their authority. Semantic operations must
therefore reject such nested contributors until their operation contract can
carry and authorize the exact Grant binding at provider and result boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.context import Context, MemoryRef


class SemanticDisclosureError(RuntimeError):
    """A readable graph contains Grant authority not represented by the caller."""


def require_semantic_disclosure_authority(
    roots: Sequence[Context],
    *,
    operation: str,
    follow_contexts: bool = True,
) -> None:
    """Reject live Grant edges reached only through a containing Context.

    A granted Context supplied as an explicit root remains available to an
    operation-aware adapter that separately froze its ``ContextAccess``. A
    granted relationship encountered below another root has no such authority
    contributor in the generic graph model and must not be relabelled local.
    """

    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("Semantic disclosure operation must be nonblank text.")
    if type(follow_contexts) is not bool:
        raise TypeError("Semantic disclosure Context reach must be a boolean.")
    frozen_roots = tuple(roots)
    if any(not isinstance(root, Context) for root in frozen_roots):
        raise TypeError("Semantic disclosure roots must be Contexts.")

    visited_contexts: set[str] = set()

    def reject(kind: str, uid: str, source_name: str, owner_name: str) -> None:
        raise SemanticDisclosureError(
            f"{operation} cannot use granted {kind} {source_name!r} "
            f"[{uid[:8]}] in Context {owner_name!r} as semantic evidence "
            "through its local owner. EMBED authorizes live reading, not "
            "provider disclosure or derived work; select the granted Source "
            "through an operation-aware authority route instead."
        )

    def visit(context: Context) -> None:
        if context.uid in visited_contexts:
            return
        visited_contexts.add(context.uid)
        for item in context.iter_items():
            if isinstance(item, MemoryRef):
                if item.is_live and item.is_granted:
                    reject(
                        "Memory Embed",
                        item.uid,
                        item.target_context_name,
                        context.name,
                    )
                continue
            if not isinstance(item, Context) or not follow_contexts:
                continue
            if item._granted_link is not None:
                # Root authorization belongs to that exact starting
                # occurrence, not to its UID globally. The same authority
                # Context may also appear below a local root or lexical peer;
                # exempting by UID would launder that nested path merely
                # because a separately selected root happened to alias it.
                reject("Context Embed", item.uid, item.name, context.name)
            visit(item)

    for root in frozen_roots:
        visit(root)


__all__ = [
    "SemanticDisclosureError",
    "require_semantic_disclosure_authority",
]
