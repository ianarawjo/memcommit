"""MemoryStore composition for terminal-independent ordinary Query answers."""

from __future__ import annotations

from typing import Protocol

from memcommit.context import Context
from memcommit.context_targeting.search import (
    collect_readable_search_candidates,
    load_readable_search_roots,
)
from memcommit.operations.query.ordinary_application import (
    FrozenOrdinaryQuerySource,
    OrdinaryQueryObserver,
    OrdinaryQueryProviderFactory,
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
    OrdinaryQuerySourcePort,
    run_ordinary_query,
)
from memcommit.store import MemoryStore


class OrdinaryQueryReadableAccess(Protocol):
    @property
    def is_granted(self) -> bool: ...


class OrdinaryQueryReadableCatalog(Protocol):
    """Narrow frozen readable namespace required by the Store adapter."""

    def list_context_names(self) -> list[str]: ...

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load(self, name: str) -> Context: ...

    def access_for(self, name: str) -> OrdinaryQueryReadableAccess: ...


class MemoryStoreOrdinaryQuerySourcePort(OrdinaryQuerySourcePort):
    """Freeze one ordinary Query frame through the readable catalog."""

    def __init__(
        self,
        store: MemoryStore,
        catalog: OrdinaryQueryReadableCatalog,
    ) -> None:
        self._store = store
        self._catalog = catalog

    def freeze(self, request: OrdinaryQueryRequest) -> FrozenOrdinaryQuerySource:
        roots = load_readable_search_roots(
            self._catalog,
            request.target_names,
            include_descendants=request.include_descendants,
            follow_embeds=request.follow_embeds,
        )
        # Profile-local artifacts never cross a READ Grant. Granted Contexts
        # contribute only the Memories and public routes exposed by the catalog.
        local_roots = tuple(
            root
            for root in roots
            if self._catalog.context_exists(root.name)
            and not self._catalog.access_for(root.name).is_granted
        )
        candidates = collect_readable_search_candidates(
            self._store,
            roots,
            follow_embeds=request.follow_embeds,
            artifact_roots=local_roots,
        )
        label = (
            request.target_names[0]
            if len(request.target_names) == 1
            else f"{len(request.target_names)} selected Contexts"
        )
        return FrozenOrdinaryQuerySource(label, tuple(candidates))


def execute_ordinary_query(
    request: OrdinaryQueryRequest,
    *,
    store: MemoryStore,
    catalog: OrdinaryQueryReadableCatalog,
    provider_factory: OrdinaryQueryProviderFactory,
    observer: OrdinaryQueryObserver | None = None,
) -> OrdinaryQueryResponse:
    """Execute ordinary Query without a CLI, TUI, or session persistence edge."""

    return run_ordinary_query(
        request,
        source_port=MemoryStoreOrdinaryQuerySourcePort(store, catalog),
        provider_factory=provider_factory,
        observer=observer,
    )


__all__ = [
    "MemoryStoreOrdinaryQuerySourcePort",
    "OrdinaryQueryReadableAccess",
    "OrdinaryQueryReadableCatalog",
    "execute_ordinary_query",
]
