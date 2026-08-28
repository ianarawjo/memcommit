"""Compatibility facade for reviewed Search result materialization."""

from __future__ import annotations

from memcommit.application.operations.search.application import SearchResponse
from memcommit.application.operations.search.materialization_application import (
    SearchMaterializationError,
    SearchMaterializationMode,
    SearchMaterializationRequest,
    SearchMaterializationResult,
)
from memcommit.application.operations.search.materialization_runtime import (
    SearchMaterializationCatalog,
    execute_search_materialization,
)
from memcommit.persistence.store import MemoryStore


def materialize_search_results(
    store: MemoryStore,
    catalog: SearchMaterializationCatalog,
    response: SearchResponse,
    *,
    selected_result_indices: tuple[int, ...],
    mode: SearchMaterializationMode,
    destination_name: str,
) -> SearchMaterializationResult:
    """Retain the historical function signature over the typed application."""

    return execute_search_materialization(
        SearchMaterializationRequest(
            response=response,
            selected_result_indices=selected_result_indices,
            mode=mode,
            destination_name=destination_name,
        ),
        store=store,
        catalog=catalog,
    )


__all__ = [
    "SearchMaterializationError",
    "SearchMaterializationMode",
    "SearchMaterializationRequest",
    "SearchMaterializationResult",
    "materialize_search_results",
]
