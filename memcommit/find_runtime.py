"""MemoryStore composition for terminal-independent semantic Search."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from memcommit.context import Context
from memcommit.context_targeting.search import (
    collect_readable_search_candidates,
    load_readable_search_roots,
)
from memcommit.find_application import (
    FindSearchObserver,
    FindSearchProviderFactory,
    FindSearchRequest,
    FindSearchResponse,
    FindSearchSourcePort,
    FrozenFindCurrentSource,
    FrozenFindHistorySource,
    run_find_search,
)
from memcommit.history import build_history
from memcommit.store import MemoryStore


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


def _history_context_names(
    catalog: FindReadableCatalog,
    roots: Sequence[Context],
    *,
    follow_embeds: bool,
) -> tuple[str, ...]:
    """Freeze history owners without opening refs or query-only sources."""

    names: list[str] = []
    visited: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited:
            return
        visited.add(context.uid)
        names.append(context.name)
        if not follow_embeds:
            return
        for item in context.iter_items():
            if isinstance(item, Context) and catalog.context_exists(item.name):
                # History is built from direct durable records. The resolved
                # graph supplies reach only; refs and query routes remain closed.
                visit(catalog.load_direct(item.name))

    for root in roots:
        visit(root)
    return tuple(names)


class MemoryStoreFindSearchSourcePort(FindSearchSourcePort):
    """Freeze current or historical evidence from one readable catalog."""

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

    def freeze_history(self, request: FindSearchRequest) -> FrozenFindHistorySource:
        roots = self._roots(request)
        names = _history_context_names(
            self._catalog,
            roots,
            follow_embeds=request.follow_embeds,
        )
        if any(self._catalog.access_for(name).is_granted for name in names):
            raise RuntimeError(
                "Temporal Search is unavailable for a granted READ view because "
                "the grant does not expose authority checkpoint history."
            )
        return FrozenFindHistorySource(
            timelines=tuple(build_history(self._store, name) for name in names)
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
