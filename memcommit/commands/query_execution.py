"""Compatibility facades for Query's terminal-independent runtimes."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.commands.readable_context_catalog import ReadableContextCatalog
from memcommit.granted_query_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQueryTarget,
)
from memcommit.granted_query_runtime import (
    CatalogLoader,
    execute_granted_query_request,
    freeze_granted_query_targets,
)
from memcommit.query_application import (
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)
from memcommit.query_runtime import execute_ordinary_query
from memcommit.query_sessions import load_authority_query_catalog
from memcommit.store import MemoryStore


StageReporter = Callable[[str, int], None]
ProviderConnector = Callable[[], object]


def run_ordinary_query_request(
    store: MemoryStore,
    catalog: ReadableContextCatalog,
    request: OrdinaryQueryRequest,
    *,
    connect_provider: ProviderConnector,
    on_stage: StageReporter | None = None,
) -> OrdinaryQueryResponse:
    """Compatibility facade over the ordinary Query application runtime."""

    def observe(stage: str) -> None:
        if on_stage is None:
            return
        if stage == "CONNECTING_PROVIDER":
            on_stage("connecting provider", 1)
        elif stage == "ANSWERING":
            on_stage("answering from complete frozen corpus", 2)

    return execute_ordinary_query(
        request,
        store=store,
        catalog=catalog,
        provider_factory=connect_provider,
        observer=observe,
    )


def run_granted_query_request(
    store: MemoryStore,
    request: GrantedQueryRequest,
    *,
    connect_provider: ProviderConnector,
    on_stage: StageReporter | None = None,
    load_catalog: CatalogLoader = load_authority_query_catalog,
) -> GrantedQueryResponse:
    """Preserve the established read-plus-optional-publication entry point."""

    def observe(stage: str) -> None:
        if on_stage is None:
            return
        if stage == "CONNECTING_PROVIDER":
            on_stage("connecting provider", 1)
        elif stage == "PREPARING_SOURCES":
            on_stage("preparing authorized sources", 2)
        elif stage == "ANSWERING":
            on_stage("answering query", 3)

    return execute_granted_query_request(
        request,
        store=store,
        provider_factory=connect_provider,
        observer=observe,
        load_catalog=load_catalog,
    )


__all__ = [
    "CatalogLoader",
    "GrantedQueryRequest",
    "GrantedQueryResponse",
    "GrantedQueryTarget",
    "OrdinaryQueryRequest",
    "OrdinaryQueryResponse",
    "freeze_granted_query_targets",
    "run_granted_query_request",
    "run_ordinary_query_request",
]
