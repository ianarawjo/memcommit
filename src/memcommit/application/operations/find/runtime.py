"""Operation-owned readable Context composition for provider-free text Find."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from memcommit.core.context import Context, Memory, MemoryRef
from memcommit.application.operations.search.source import load_readable_search_roots
from memcommit.application.operations.find.application import (
    FrozenFindSource,
    FindRequest,
    FindResult,
    FindSourceItem,
    FindSourcePort,
    run_find,
)


class FindReadableAccess(Protocol):
    @property
    def is_granted(self) -> bool: ...


class FindReadableCatalog(Protocol):
    """Narrow readable namespace used by deterministic Find."""

    def list_context_names(self) -> list[str]: ...

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load(self, name: str) -> Context: ...

    def access_for(self, name: str) -> FindReadableAccess: ...


def collect_find_sources(
    roots: Sequence[Context],
    *,
    follow_embeds: bool,
    catalog: FindReadableCatalog,
) -> tuple[FindSourceItem, ...]:
    """Freeze ordinary Memories and resolved MemoryRefs in stable graph order."""

    sources: list[FindSourceItem] = []
    visited_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited_contexts:
            return
        visited_contexts.add(context.uid)
        for item in context.iter_items():
            if isinstance(item, Memory):
                sources.append(
                    FindSourceItem(
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
                if target is None and catalog.context_exists(item.target_context_name):
                    source = catalog.load_direct(item.target_context_name)
                    candidate = source.memories.get(item.target_memory_uid)
                    if source.uid == item.target_context_uid and isinstance(
                        candidate, Memory
                    ):
                        target = candidate
                if target is None:
                    continue
                sources.append(
                    FindSourceItem(
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


class ReadableFindSourcePort(FindSourcePort):
    """Load one already frozen readable namespace for deterministic matching."""

    def __init__(self, catalog: FindReadableCatalog) -> None:
        self._catalog = catalog

    def freeze(self, request: FindRequest) -> FrozenFindSource:
        roots = load_readable_search_roots(
            self._catalog,
            request.target_names,
            include_descendants=request.include_descendants,
            follow_embeds=request.follow_embeds,
        )
        return FrozenFindSource(
            collect_find_sources(
                roots,
                follow_embeds=request.follow_embeds,
                catalog=self._catalog,
            )
        )


def execute_find(
    request: FindRequest,
    *,
    catalog: FindReadableCatalog,
) -> FindResult:
    """Run deterministic Find against one authorized readable catalog."""

    return run_find(
        request,
        source_port=ReadableFindSourcePort(catalog),
    )


__all__ = [
    "ReadableFindSourcePort",
    "FindReadableAccess",
    "FindReadableCatalog",
    "collect_find_sources",
    "execute_find",
]
