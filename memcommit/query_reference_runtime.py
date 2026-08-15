"""MemoryStore adapter for terminal-independent QueryContextRef reads."""

from __future__ import annotations

from memcommit.query_reference_application import (
    FrozenQueryReferenceSource,
    QueryReferenceObserver,
    QueryReferenceProviderFactory,
    QueryReferenceRequest,
    QueryReferenceResponse,
    QueryReferenceSourcePort,
    run_query_reference,
)
from memcommit.store import MemoryStore


class MemoryStoreQueryReferenceSourcePort(QueryReferenceSourcePort):
    """Open the legacy concealed Source selected by one exact reference."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def open(self, request: QueryReferenceRequest) -> FrozenQueryReferenceSource:
        source = self._store.load_query_source(
            request.source_uid,
            expected_name=request.source_name,
            language=request.language,
        )
        return FrozenQueryReferenceSource(source.name, source.content)


def execute_query_reference(
    request: QueryReferenceRequest,
    *,
    store: MemoryStore,
    provider_factory: QueryReferenceProviderFactory,
    observer: QueryReferenceObserver | None = None,
) -> QueryReferenceResponse:
    """Execute one unsaved QueryContextRef answer through the Store adapter."""

    return run_query_reference(
        request,
        source_port=MemoryStoreQueryReferenceSourcePort(store),
        provider_factory=provider_factory,
        observer=observer,
    )


__all__ = [
    "MemoryStoreQueryReferenceSourcePort",
    "execute_query_reference",
]
