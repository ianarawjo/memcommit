"""Operation-owned MemoryStore composition for semantic Search."""

from __future__ import annotations

from typing import Protocol

from memcommit.application.context_access.access import ContextAccess
from memcommit.models.context import Context
from memcommit.application.capabilities.retrieval_corpus.loading import (
    collect_readable_corpus_candidates,
    load_readable_corpus_roots,
)
from memcommit.application.operations.search.application import (
    SearchObserver,
    SearchProviderFactory,
    SearchRequest,
    SearchResponse,
    SearchSourcePort,
    FrozenSearchCurrentSource,
    run_search,
)
from memcommit.persistence.store import MemoryStore


class SearchReadableCatalog(Protocol):
    """Narrow frozen readable namespace required by the Store adapter."""

    def list_context_names(self) -> list[str]: ...

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load(self, name: str) -> Context: ...

    def access_for(self, name: str) -> ContextAccess: ...


class MemoryStoreSearchSourcePort(SearchSourcePort):
    """Freeze current readable evidence from one catalog."""

    def __init__(self, store: MemoryStore, catalog: SearchReadableCatalog):
        self._store = store
        self._catalog = catalog

    def _roots(self, request: SearchRequest) -> tuple[Context, ...]:
        return load_readable_corpus_roots(
            self._catalog,
            request.target_names,
            include_descendants=request.include_descendants,
        )

    def freeze_current(self, request: SearchRequest) -> FrozenSearchCurrentSource:
        roots = self._roots(request)
        candidates = collect_readable_corpus_candidates(
            self._store,
            roots,
            artifact_roots=roots,
            operation="Search",
        )
        coverage_root_name = (
            request.target_names[0]
            if len(request.target_names) == 1 and request.include_descendants
            else None
        )
        return FrozenSearchCurrentSource(
            candidates=candidates,
            coverage_root_name=coverage_root_name,
        )


def execute_search(
    request: SearchRequest,
    *,
    store: MemoryStore,
    catalog: SearchReadableCatalog,
    provider_factory: SearchProviderFactory,
    observer: SearchObserver | None = None,
) -> SearchResponse:
    """Execute Search with no argv, terminal, clipboard, or materialization edge."""

    return run_search(
        request,
        source_port=MemoryStoreSearchSourcePort(store, catalog),
        provider_factory=provider_factory,
        observer=observer,
    )


__all__ = [
    "ContextAccess",
    "SearchReadableCatalog",
    "MemoryStoreSearchSourcePort",
    "execute_search",
]
