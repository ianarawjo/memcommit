"""Authority-neutral loading for one merged Context scope."""

from __future__ import annotations

from typing import Protocol

from memcommit.context import Context, Memory
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.model import (
    ContextScope,
    DirectMemoryTarget,
)
from memcommit.context_targeting.resolution import (
    expand_lexical_context_names,
    parse_direct_memory_locator,
)


class ReadableContextScopeStore(Protocol):
    """Minimal owned-store or Grant-view surface needed for merged loading."""

    def load(self, name: str) -> Context: ...

    def list_context_names(self) -> list[str]: ...


class LocalDirectMemoryLocatorStore(Protocol):
    """Complete ordinary-local surface used for exact Memory owner lookup."""

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load_direct_context_graph_strict(self) -> tuple[Context, ...]: ...


def _direct_memory_matches(
    context: Context,
    selector: str,
) -> tuple[Memory, ...]:
    return tuple(
        item
        for item in context.iter_items()
        if isinstance(item, Memory) and item.uid.startswith(selector)
    )


def _resolved_direct_memory_target(
    selector: str,
    matches: tuple[tuple[Context, Memory], ...],
    *,
    context_name: str | None,
) -> DirectMemoryTarget:
    if not matches:
        if context_name is not None:
            raise ValueError(
                f"No directly owned Memory with uid starting with {selector!r} "
                f"exists in Context {context_name!r}."
            )
        raise ValueError(
            f"No directly owned Memory with uid starting with {selector!r} "
            "was found in any local Context."
        )
    if len(matches) > 1:
        choices = "; ".join(
            f"{context.name}:{memory.uid}"
            for context, memory in sorted(
                matches,
                key=lambda match: (match[0].name.casefold(), match[1].uid),
            )
        )
        raise ValueError(
            f"Memory prefix {selector!r} has multiple local matches "
            f"({len(matches)}): {choices}. "
            "Use one qualified CONTEXT:UID locator."
        )
    context, memory = matches[0]
    return DirectMemoryTarget(context.name, memory.uid)


def resolve_local_direct_memory_locator(
    store: LocalDirectMemoryLocatorStore,
    operand: object,
    *,
    current: str | None,
    explicit_context: str | None = None,
) -> DirectMemoryTarget:
    """Resolve one exact ordinary local owner without hidden current priority.

    A qualified locator searches only its canonical direct owner. A bare
    selector scans one strict snapshot of every ordinary local direct record;
    exactly one match is required even when one match happens to be current.
    MemoryRefs, snapshots, embedded traversal, and Grant content never enter
    this local ownership catalog.
    """

    locator = parse_direct_memory_locator(
        operand,
        explicit_context=explicit_context,
    )
    if locator.context_locator is not None:
        context_name = resolve_context_locator(
            locator.context_locator,
            current=current,
        )
        if not store.context_exists(context_name):
            raise FileNotFoundError(
                f"Context {context_name!r} does not exist locally."
            )
        context = store.load_direct(context_name)
        matches = tuple(
            (context, memory)
            for memory in _direct_memory_matches(
                context,
                locator.memory_selector,
            )
        )
        return _resolved_direct_memory_target(
            locator.memory_selector,
            matches,
            context_name=context_name,
        )

    matches = tuple(
        (context, memory)
        for context in store.load_direct_context_graph_strict()
        for memory in _direct_memory_matches(context, locator.memory_selector)
    )
    return _resolved_direct_memory_target(
        locator.memory_selector,
        matches,
        context_name=None,
    )


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
