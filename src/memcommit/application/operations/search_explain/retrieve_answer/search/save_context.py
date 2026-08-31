"""Adapt a reviewed Search result set to the shared Context-save capability."""

from __future__ import annotations

from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextFromSelectionError,
    SaveContextFromSelectionRequest,
    SaveContextMode,
    SelectedMemory,
    SelectionOrigin,
)
from memcommit.application.operations.search_explain.retrieve_answer.search.application import SearchResponse
from memcommit.application.operations.search_explain.retrieve_answer.selection_save import (
    RetrieveAnswerSelectionCatalog,
    resolve_selection_source_public_name,
)


SearchSelectionCatalog = RetrieveAnswerSelectionCatalog


def save_context_request_from_search(
    response: SearchResponse,
    selected_result_indices: tuple[int, ...],
    *,
    mode: SaveContextMode,
    destination_name: str,
    catalog: SearchSelectionCatalog,
) -> SaveContextFromSelectionRequest:
    """Translate exact Search rows without giving the shared saver Search types."""

    if not isinstance(response, SearchResponse):
        raise SaveContextFromSelectionError(
            "Saving Search results requires one typed Search response."
        )
    if not selected_result_indices:
        raise SaveContextFromSelectionError("Check at least one Search result.")
    if len(set(selected_result_indices)) != len(selected_result_indices) or any(
        isinstance(index, bool)
        or not isinstance(index, int)
        or not 0 <= index < len(response.results)
        for index in selected_result_indices
    ):
        raise SaveContextFromSelectionError(
            "Search selected an invalid result row."
        )

    selection: list[SelectedMemory] = []
    for index in selected_result_indices:
        result = response.results[index]
        if result.kind not in {"memory", "ref"}:
            raise SaveContextFromSelectionError(
                f"{result.kind} results cannot be saved as Memory selections."
            )
        if not (
            result.source_context_name
            and result.source_context_uid
            and result.source_memory_uid
        ):
            raise SaveContextFromSelectionError(
                "This Search result has no frozen source-Memory identity."
            )
        source_name = resolve_selection_source_public_name(
            catalog,
            containing_name=result.context_name,
            source_name=result.source_context_name,
            is_reference=result.kind == "ref",
        )
        selection.append(
            SelectedMemory(
                position=index + 1,
                source_kind=result.kind,
                source_context_name=source_name,
                source_context_uid=result.source_context_uid,
                source_memory_uid=result.source_memory_uid,
                content=result.content,
                relevance=result.relevance,
            )
        )

    return SaveContextFromSelectionRequest(
        selection=tuple(selection),
        mode=mode,
        destination_name=destination_name,
        origin=SelectionOrigin(
            operation="search",
            arguments=(("query", response.request.query),),
        ),
    )


__all__ = ["SearchSelectionCatalog", "save_context_request_from_search"]
