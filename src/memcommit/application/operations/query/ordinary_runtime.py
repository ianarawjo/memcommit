"""ProfileStore composition for terminal-independent ordinary Query answers."""

from __future__ import annotations

from typing import Protocol

from memcommit.application.context_access.access import ContextAccess
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.models.context import Context
from memcommit.application.capabilities.retrieval_corpus.loading import (
    collect_readable_corpus_candidates,
    load_readable_corpus_roots,
)
from memcommit.application.operations.query.ordinary_application import (
    FrozenOrdinaryQuerySource,
    OrdinaryQueryObserver,
    OrdinaryQueryProviderFactory,
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
    OrdinaryQuerySourcePort,
    run_ordinary_query,
)
from memcommit.persistence.store import ProfileStore


class OrdinaryQueryReadableCatalog(Protocol):
    """Narrow frozen readable namespace required by the Store adapter."""

    def list_context_names(self) -> list[str]: ...

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load(self, name: str) -> Context: ...

    def access_for(self, name: str) -> ContextAccess: ...


class MemoryStoreOrdinaryQuerySourcePort(OrdinaryQuerySourcePort):
    """Freeze one ordinary Query frame through the readable catalog."""

    def __init__(
        self,
        store: ProfileStore,
        catalog: OrdinaryQueryReadableCatalog,
    ) -> None:
        self._store = store
        self._catalog = catalog

    def freeze(self, request: OrdinaryQueryRequest) -> FrozenOrdinaryQuerySource:
        roots = load_readable_corpus_roots(
            self._catalog,
            request.target_names,
            include_descendants=request.include_descendants,
        )
        candidates = collect_readable_corpus_candidates(
            self._store,
            roots,
            artifact_roots=roots,
            operation="Query",
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
    store: ProfileStore,
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


def execute_profile_query(
    question: str,
    *,
    store: ProfileStore,
    provider_factory: OrdinaryQueryProviderFactory,
    observer: OrdinaryQueryObserver | None = None,
) -> OrdinaryQueryResponse:
    """Answer from every Context in the active Profile, independent of current."""

    catalog = freeze_profile_readable_context_catalog(store)
    context_names = tuple(catalog.list_context_names())
    if not context_names:
        raise ValueError("No Contexts are available for Query in this Profile.")
    return execute_ordinary_query(
        OrdinaryQueryRequest(question=question, target_names=context_names),
        store=store,
        catalog=catalog,
        provider_factory=provider_factory,
        observer=observer,
    )


__all__ = [
    "MemoryStoreOrdinaryQuerySourcePort",
    "ContextAccess",
    "OrdinaryQueryReadableCatalog",
    "execute_ordinary_query",
    "execute_profile_query",
]
