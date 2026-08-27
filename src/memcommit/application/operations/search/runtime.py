"""Operation-owned MemoryStore composition for semantic Search."""

from __future__ import annotations

from typing import Protocol

from memcommit.context import Context
from memcommit.core.context_targeting.search import (
    collect_readable_search_candidates,
    load_readable_search_roots,
)
from memcommit.application.operations.search.application import (
    FindSearchObserver,
    FindSearchProviderFactory,
    FindSearchRequest,
    FindSearchResponse,
    FindSearchSourcePort,
    FrozenFindCurrentSource,
    run_find_search,
)
from memcommit.persistence.store import MemoryStore


class FindReadableAccess(Protocol):
    @property
    def is_granted(self) -> bool: ...


class FindReadableCatalog(Protocol):
    """Narrow frozen readable namespace required by the Store adapter."""

    def list_context_names(self) -> list[str]: ...

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load(self, name: str) -> Context: ...

    def load_without_attached_reads(self, name: str) -> Context: ...

    def access_for(self, name: str) -> FindReadableAccess: ...


class MemoryStoreFindSearchSourcePort(FindSearchSourcePort):
    """Freeze current readable evidence from one catalog."""

    def __init__(self, store: MemoryStore, catalog: FindReadableCatalog):
        self._store = store
        self._catalog = catalog

    def _roots(self, request: FindSearchRequest) -> tuple[Context, ...]:
        return load_readable_search_roots(
            self._catalog,
            request.target_names,
            include_descendants=request.include_descendants,
            follow_embeds=request.follow_embeds,
            include_attached_reads=False,
        )

    def freeze_current(self, request: FindSearchRequest) -> FrozenFindCurrentSource:
        roots = self._roots(request)
        # Profile-local artifacts never cross a READ Grant. Granted Contexts
        # can contribute their authorized Memories and public query routes only.
        local_roots: list[Context] = []
        for root in roots:
            try:
                access = self._catalog.access_for(root.name)
            except FileNotFoundError:
                # An embedded Context can be readable through its parent graph
                # without being an independently addressable public catalog row.
                continue
            if not access.is_granted:
                local_roots.append(root)
        candidates = collect_readable_search_candidates(
            self._store,
            roots,
            follow_embeds=request.follow_embeds,
            artifact_roots=tuple(local_roots),
        )
        coverage_root_name = (
            request.target_names[0]
            if len(request.target_names) == 1 and request.include_descendants
            else None
        )
        return FrozenFindCurrentSource(
            candidates=candidates,
            coverage_root_name=coverage_root_name,
        )

def execute_find_search(
    request: FindSearchRequest,
    *,
    store: MemoryStore,
    catalog: FindReadableCatalog,
    provider_factory: FindSearchProviderFactory,
    observer: FindSearchObserver | None = None,
) -> FindSearchResponse:
    """Execute Search with no argv, terminal, clipboard, or materialization edge."""

    return run_find_search(
        request,
        source_port=MemoryStoreFindSearchSourcePort(store, catalog),
        provider_factory=provider_factory,
        observer=observer,
    )


__all__ = [
    "FindReadableAccess",
    "FindReadableCatalog",
    "MemoryStoreFindSearchSourcePort",
    "execute_find_search",
]
