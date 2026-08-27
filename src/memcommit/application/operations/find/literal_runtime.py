"""Operation-owned readable Context composition for provider-free text Find."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from memcommit.context import Context, Memory, MemoryRef
from memcommit.core.context_targeting.search import load_readable_search_roots
from memcommit.application.operations.find.literal_application import (
    FrozenLiteralFindSource,
    LiteralFindRequest,
    LiteralFindResult,
    LiteralFindSourceItem,
    LiteralFindSourcePort,
    run_literal_find,
)


class LiteralFindReadableAccess(Protocol):
    @property
    def is_granted(self) -> bool: ...


class LiteralFindReadableCatalog(Protocol):
    """Narrow readable namespace used by deterministic Find."""

    def list_context_names(self) -> list[str]: ...

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load(self, name: str) -> Context: ...

    def access_for(self, name: str) -> LiteralFindReadableAccess: ...


def collect_literal_find_sources(
    roots: Sequence[Context],
    *,
    follow_embeds: bool,
    catalog: LiteralFindReadableCatalog,
) -> tuple[LiteralFindSourceItem, ...]:
    """Freeze ordinary Memories and resolved MemoryRefs in stable graph order."""

    sources: list[LiteralFindSourceItem] = []
    visited_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited_contexts:
            return
        visited_contexts.add(context.uid)
        for item in context.iter_items():
            if isinstance(item, Memory):
                sources.append(
                    LiteralFindSourceItem(
                        context_name=context.name,
                        context_uid=context.uid,
                        kind="memory",
                        item_uid=item.uid,
                        source_position=len(sources) + 1,
                        content=item.content,
                    )
                )
            elif isinstance(item, MemoryRef):
                target = item.target
                if target is None and catalog.context_exists(
                    item.target_context_name
                ):
                    source = catalog.load_direct(item.target_context_name)
                    candidate = source.memories.get(item.target_memory_uid)
                    if (
                        source.uid == item.target_context_uid
                        and isinstance(candidate, Memory)
                    ):
                        target = candidate
                if target is None:
                    continue
                sources.append(
                    LiteralFindSourceItem(
                        context_name=context.name,
                        context_uid=context.uid,
                        kind="memory_ref",
                        item_uid=item.uid,
                        source_position=len(sources) + 1,
                        content=target.content,
                        source_context_name=item.target_context_name,
                        source_context_uid=item.target_context_uid,
                        source_memory_uid=item.target_memory_uid,
                    )
                )
            elif isinstance(item, Context) and follow_embeds:
                visit(item)

    for root in roots:
        visit(root)
    return tuple(sources)


class ReadableLiteralFindSourcePort(LiteralFindSourcePort):
    """Load one already frozen readable namespace for deterministic matching."""

    def __init__(self, catalog: LiteralFindReadableCatalog) -> None:
        self._catalog = catalog

    def freeze(self, request: LiteralFindRequest) -> FrozenLiteralFindSource:
        roots = load_readable_search_roots(
            self._catalog,
            request.target_names,
            include_descendants=request.include_descendants,
            follow_embeds=request.follow_embeds,
        )
        return FrozenLiteralFindSource(
            collect_literal_find_sources(
                roots,
                follow_embeds=request.follow_embeds,
                catalog=self._catalog,
            )
        )


def execute_literal_find(
    request: LiteralFindRequest,
    *,
    catalog: LiteralFindReadableCatalog,
) -> LiteralFindResult:
    """Run deterministic Find against one authorized readable catalog."""

    return run_literal_find(
        request,
        source_port=ReadableLiteralFindSourcePort(catalog),
    )


__all__ = [
    "ReadableLiteralFindSourcePort",
    "LiteralFindReadableAccess",
    "LiteralFindReadableCatalog",
    "collect_literal_find_sources",
    "execute_literal_find",
]
