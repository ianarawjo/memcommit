"""Authority-neutral loading for one merged Context scope."""

from __future__ import annotations

from typing import Protocol

from memcommit.context import Context
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.resolution import expand_lexical_context_names


class ReadableContextScopeStore(Protocol):
    """Minimal owned-store or Grant-view surface needed for merged loading."""

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
