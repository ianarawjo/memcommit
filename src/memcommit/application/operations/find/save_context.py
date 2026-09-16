"""Adapt reviewed Find matches to the shared Context-save capability."""

from __future__ import annotations

from memcommit.application.capabilities.save_context_from_selection.application import (
    SaveContextFromSelectionError,
    SaveContextFromSelectionRequest,
    SaveContextMode,
    SelectedMemory,
    SelectionOrigin,
)
from memcommit.application.operations.find.application import (
    FindResult,
)
from memcommit.application.capabilities.save_context_from_selection.source_resolution import (
    RetrieveAnswerSelectionCatalog,
    resolve_selection_source_public_name,
)


FindSelectionCatalog = RetrieveAnswerSelectionCatalog


def save_context_request_from_find(
    result: FindResult,
    selected_match_indices: tuple[int, ...],
    *,
    mode: SaveContextMode,
    destination_name: str,
    catalog: FindSelectionCatalog,
) -> SaveContextFromSelectionRequest:
    """Translate exact Find match rows without leaking Find types downstream."""

    if not isinstance(result, FindResult):
        raise SaveContextFromSelectionError(
            "Saving Find results requires one typed Find result."
        )
    if not selected_match_indices:
        raise SaveContextFromSelectionError("Check at least one Find match.")
    if len(set(selected_match_indices)) != len(selected_match_indices) or any(
        isinstance(index, bool)
        or not isinstance(index, int)
        or not 0 <= index < len(result.matches)
        for index in selected_match_indices
    ):
        raise SaveContextFromSelectionError("Find selected an invalid match row.")

    selection: list[SelectedMemory] = []
    for index in selected_match_indices:
        match = result.matches[index]
        source = match.source
        if source.kind == "memory":
            source_name = source.context_name
            source_context_uid = source.context_uid
            source_memory_uid = source.item_uid
        else:
            if not (
                source.source_context_name
                and source.source_context_uid
                and source.source_memory_uid
            ):
                raise SaveContextFromSelectionError(
                    "This Find match has no frozen source-Memory identity."
                )
            source_name = source.source_context_name
            source_context_uid = source.source_context_uid
            source_memory_uid = source.source_memory_uid
        public_name = resolve_selection_source_public_name(
            catalog,
            containing_name=source.context_name,
            source_name=source_name,
            is_reference=source.kind == "memory_ref",
        )
        selection.append(
            SelectedMemory(
                position=index + 1,
                source_kind=source.kind,
                source_context_name=public_name,
                source_context_uid=source_context_uid,
                source_memory_uid=source_memory_uid,
                content=source.content,
            )
        )

    return SaveContextFromSelectionRequest(
        selection=tuple(selection),
        mode=mode,
        destination_name=destination_name,
        origin=SelectionOrigin(
            operation="find",
            arguments=(
                ("pattern", result.request.pattern),
                ("mode", result.request.mode),
                ("ignore_case", str(result.request.ignore_case).lower()),
            ),
        ),
    )


__all__ = ["FindSelectionCatalog", "save_context_request_from_find"]
