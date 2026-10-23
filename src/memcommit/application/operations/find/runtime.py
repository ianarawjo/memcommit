"""Operation-owned readable Context composition for provider-free text Find."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from memcommit.application.context_access.access import ContextAccess
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.capabilities.retrieval_corpus.loading import (
    load_readable_corpus_roots,
)
from memcommit.application.operations.find.application import (
    FrozenFindSource,
    FindRequest,
    FindResult,
    FindSourceItem,
    FindSourcePort,
    run_find,
)


class FindReadableCatalog(Protocol):
    """Narrow readable namespace used by deterministic Find."""

    def list_context_names(self) -> list[str]: ...

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load(self, name: str) -> Context: ...

    def access_for(self, name: str) -> ContextAccess: ...


def collect_find_sources(
    roots: Sequence[Context],
    *,
    catalog: FindReadableCatalog,
) -> tuple[FindSourceItem, ...]:
    """Freeze owned Memories in stable Context and item order."""

    sources: list[FindSourceItem] = []
    visited_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited_contexts:
            return
        visited_contexts.add(context.uid)
        for item in context.iter_memories():
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

    for root in roots:
        visit(root)
    return tuple(sources)


class ReadableFindSourcePort(FindSourcePort):
    """Load one already frozen readable namespace for deterministic matching."""

    def __init__(self, catalog: FindReadableCatalog) -> None:
        self._catalog = catalog

    def freeze(self, request: FindRequest) -> FrozenFindSource:
        roots = load_readable_corpus_roots(
            self._catalog,
            request.target_names,
            include_descendants=request.include_descendants,
        )
        return FrozenFindSource(
            collect_find_sources(
                roots,
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
    "ContextAccess",
    "FindReadableCatalog",
    "collect_find_sources",
    "execute_find",
]
