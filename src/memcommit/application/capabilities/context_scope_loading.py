"""Load one operation-ready Context graph from a readable scope."""

from __future__ import annotations

from typing import Protocol

from memcommit.core.context import Context
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names


class ReadableContextScopeStore(Protocol):
    """Minimal owned-store or Grant-view surface needed for scoped loading."""

    def load(self, name: str) -> Context: ...

    def list_context_names(self) -> list[str]: ...


def _context_uids(root: Context) -> set[str]:
    seen: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in seen:
            return
        seen.add(context.uid)
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    return seen


def load_context_scope(
    store: ReadableContextScopeStore,
    root_name: str,
    *,
    include_descendants: bool,
) -> Context:
    """Load one graph, optionally widening it to every lexical descendant.

    The supplied store defines the authority boundary. It may be an ordinary
    owned ``MemoryStore`` or a frozen read-only Grant projection; attachment
    metadata is never interpreted as a hierarchy edge. Explicit embedded
    Context edges are already followed by ``load`` and UID de-duplication keeps
    a Context that is also visible lexically from entering the frame twice.
    """

    scope = ContextScope.create(
        (root_name,),
        include_descendants=include_descendants,
    )
    root = store.load(root_name)
    if not scope.include_descendants:
        return root
    names = expand_lexical_context_names(
        scope,
        sorted(store.list_context_names(), key=str.casefold),
    )
    known_uids = _context_uids(root)
    for name in names[1:]:
        descendant = store.load(name)
        if descendant.uid in known_uids:
            continue
        root.add(descendant)
        known_uids.update(_context_uids(descendant))
    return root


def walk_context_owners(root: Context) -> tuple[Context, ...]:
    """Keep one occurrence of every real owner in a loaded target graph."""
    owners = []
    seen = set()

    def visit(context):
        if context.uid in seen:
            return
        seen.add(context.uid)
        owners.append(context)
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    return tuple(owners)


def load_mutable_context_scope(active_store, root_access, *, registry=None) -> Context:
    """Load recursive targets through their exact readable namespace bindings."""
    from memcommit.application.context_access.access import resolve_context_access
    from memcommit.application.context_access.readable_contexts import (
        freeze_readable_context_catalog,
    )

    catalog = freeze_readable_context_catalog(
        active_store, root_access, include_query_routes=False, registry=registry
    )
    root = load_context_scope(
        catalog, root_access.access_name, include_descendants=True
    )
    for owner in walk_context_owners(root):
        access = catalog.access_for(owner.name)
        if root_access.is_granted:
            # Root-bound catalogs reuse the root access for their rows. Resolve
            # each name so child placements cannot inherit its mutation authority.
            access = resolve_context_access(
                active_store,
                owner.name,
                current_name=None,
                required_permission="READ",
                registry=registry,
            )
        # Readable breadth can cross authorities; the existing multi-owner
        # publisher writes under one Store and one exact Target Grant.
        if (
            access.store.store_dir != root_access.store.store_dir
            or access.is_granted != root_access.is_granted
        ):
            raise ValueError(
                "Recursive mutation cannot span different Context authorities."
            )
        if access.is_granted and access.view.grant.uid != root_access.view.grant.uid:
            raise ValueError("Recursive mutation requires one frozen Target Grant.")
    return root
