"""Console provider composition and static Search progress."""

from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
)
from memcommit.application.operations.search.application import (
    SearchObserver,
    SearchRequest,
    SearchResponse,
    SearchStage,
)
from memcommit.application.operations.search.runtime import execute_search
from memcommit.providers.connection import connect_search_provider
from memcommit.persistence.store import MemoryStore
from memcommit.adapters.console.terminal.components.progress import CommandProgress


def run_search_request(
    store: MemoryStore,
    catalog: ReadableContextCatalog,
    request: SearchRequest,
    *,
    observer: SearchObserver | None = None,
) -> SearchResponse:
    """Connect the configured provider to the terminal-independent Search runtime."""

    return execute_search(
        request,
        store=store,
        catalog=catalog,
        provider_factory=connect_search_provider,
        observer=observer,
    )


def run_static_search(
    store: MemoryStore,
    catalog: ReadableContextCatalog,
    request: SearchRequest,
    *,
    show_progress: bool,
) -> SearchResponse:
    """Adapt application stages without making catalog selection an execution branch."""

    if not show_progress:
        return run_search_request(store, catalog, request)
    with CommandProgress("SEARCH", "connecting provider", total=3) as progress:

        def observe(stage: SearchStage) -> None:
            if stage == "SEARCHING":
                progress.update("ranking candidates", step=2)
            elif stage == "CHECKING_COVERAGE":
                progress.update("checking namespace coverage", step=3)

        return run_search_request(store, catalog, request, observer=observe)
