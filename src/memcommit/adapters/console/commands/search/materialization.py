"""Compatibility facade for reviewed Find result materialization."""

from __future__ import annotations

from memcommit.application.operations.search.application import FindSearchResponse
from memcommit.application.operations.search.materialization_application import (
    FindMaterializationError,
    FindMaterializationMode,
    FindMaterializationRequest,
    FindMaterializationResult,
)
from memcommit.application.operations.search.materialization_runtime import (
    FindMaterializationCatalog,
    execute_find_materialization,
)
from memcommit.persistence.store import MemoryStore


def materialize_find_results(
    store: MemoryStore,
    catalog: FindMaterializationCatalog,
    response: FindSearchResponse,
    *,
    selected_result_indices: tuple[int, ...],
    mode: FindMaterializationMode,
    destination_name: str,
) -> FindMaterializationResult:
    """Retain the historical function signature over the typed application."""

    return execute_find_materialization(
        FindMaterializationRequest(
            response=response,
            selected_result_indices=selected_result_indices,
            mode=mode,
            destination_name=destination_name,
        ),
        store=store,
        catalog=catalog,
    )


__all__ = [
    "FindMaterializationError",
    "FindMaterializationMode",
    "FindMaterializationRequest",
    "FindMaterializationResult",
    "materialize_find_results",
]
